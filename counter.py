# coding: utf-8

import sys
import argparse

from datetime import timedelta

from tinkoff.invest import utils as tiu
# candle_interval_to_timedelta,
# ceil_datetime,
# floor_datetime,
#     now,
# )

from tinkoff.invest import Client
from tinkoff.invest import GetOperationsByCursorRequest
from tinkoff.invest import OperationState
from tinkoff.invest import OperationType

# from tinkoff.invest import

# from google.protobuf.timestamp_pb2 import Timestamp


import utils as u

_TOKEN = open(".token.txt").read().strip()
_PAPERS_BLACKLIST = u.tokenize_file("papers_blacklist.ini", ignore_comments=True)

unique_names = set()

NANOS_IN_ONE = 1_000_000_000


class Item(object):
    def __init__(self, name, figi):
        self.name = name
        self.figi = figi


class Amount(object):
    def __init__(self, units=0, nano=0, quantity=None):
        self.op_counter = 0
        if quantity is not None:
            self.units = quantity.units
            self.nano = quantity.nano
            assert units == 0 and nano == 0
            return

        self.units = units
        self.nano = nano

    def add(self, other, inc_counter=True):
        self.units += other.units
        self.nano += other.nano
        if inc_counter:
            self.op_counter += 1

        # normalize money
        while abs(self.nano) > NANOS_IN_ONE:
            if self.nano >= NANOS_IN_ONE:
                self.units += 1
                self.nano -= NANOS_IN_ONE

            if self.nano <= -NANOS_IN_ONE:
                self.units -= 1
                self.nano += NANOS_IN_ONE

    def __str__(self):
        return "{:20.2f}".format(self.units + self.nano / float(NANOS_IN_ONE))


class ItemStore(object):
    def __init__(self):
        self.store_by_figi = {}
        self.figi_to_name = {}

    def add_op(self, item):
        if item.figi not in self.store_by_figi:
            self.store_by_figi[item.figi] = Amount()

        self.figi_to_name[item.figi] = item.name
        # if item.name not in self.store_by_name:
        #    self.store_by_name[item.name] = Amount()

        # self.op_counter += 1
        self.store_by_figi[item.figi].add(Amount(quantity=item.payment))
        self.store_by_figi[item.figi].add(Amount(quantity=item.commission))

    def dump(self):
        for figi, item in self.store_by_figi.items():
            print(figi, item, item.op_counter)
        print()


def calculate_total_profit(client, days=30, verbose_level=0):
    print("Days ago to count from: {}".format(days))

    accs = client.users.get_accounts()
    a = accs.accounts[0]
    # print(a)

    item_store = ItemStore()

    portfolio = client.operations.get_portfolio(account_id=a.id)

    for position in portfolio.positions:
        if position.blocked:
            continue

        if position.current_price.currency != 'rub':
            continue

        if position.instrument_type != 'share':
            continue

        print(position)
        print()

    def get_request(cursor=""):
        return GetOperationsByCursorRequest(
            account_id=a.id,
            cursor=cursor,
            from_=tiu.now() - timedelta(days=days),
        )

    operations = client.operations.get_operations_by_cursor(get_request())
    total_units = 0
    total_nano = 0

    total_commission_units = 0
    total_commission_nano = 0

    sum_by_name_units = {}
    sum_by_name_nano = {}

    op_counter = 0
    while True:
        for item in operations.items:
            op_counter += 1
            if verbose_level > 0 and op_counter % 10 == 0:
                sys.stdout.write(".")
                sys.stdout.flush()

            # apply some filters
            if item.state == OperationState.OPERATION_STATE_CANCELED:
                continue

            if item.payment.currency != "rub":
                continue

            # count divs unconditionally
            if (
                item.name in _PAPERS_BLACKLIST and
                item.type not in [
                    OperationType.OPERATION_TYPE_DIVIDEND,
                    OperationType.OPERATION_TYPE_DIVIDEND_TAX,
                ]
            ):
                continue

            # skip miserable overnights, inputs, outputs and taxes
            if not item.name and (
                item.type == OperationType.OPERATION_TYPE_INPUT or
                item.type == OperationType.OPERATION_TYPE_OUTPUT or
                item.type == OperationType.OPERATION_TYPE_TAX or
                item.type == OperationType.OPERATION_TYPE_OVERNIGHT
            ):
                continue

            name = item.name
            if (
                item.type == OperationType.OPERATION_TYPE_DIVIDEND or
                item.type == OperationType.OPERATION_TYPE_DIVIDEND_TAX
            ):
                name = "DIV"

            if (
                item.type == OperationType.OPERATION_TYPE_WRITING_OFF_VARMARGIN or
                item.type == OperationType.OPERATION_TYPE_MARGIN_FEE
            ):
                continue

            if not name:
                print(item)
                assert False

            print(item.figi)

            unique_names.add(name)

            units = item.payment.units + item.commission.units
            nano = item.payment.nano + item.commission.nano

            # new
            item_store.add_op(item)

            total_units += units
            total_nano += nano

            total_commission_units += item.commission.units
            total_commission_nano += item.commission.nano

            if name not in sum_by_name_units:
                sum_by_name_units[name] = 0

            if name not in sum_by_name_nano:
                sum_by_name_nano[name] = 0

            sum_by_name_units[name] += units
            sum_by_name_nano[name] += nano

        if not operations.next_cursor:
            break

        request = get_request(cursor=operations.next_cursor)
        operations = client.operations.get_operations_by_cursor(request)

    sys.stdout.write("\n")

    print("=" * 60)

    ordered_by_sum = sorted(
        [
            (name, amount)
            for name, amount in sum_by_name_units.items()
        ],
        key=lambda x: x[1],
        reverse=True,
    )

    for name, amount in ordered_by_sum:
        print("{:50}{:10}".format(name, amount))

    print("=" * 60)

    print("{:50}{:10.2f}".format("Total mined:", total_units))
    print("{:50}{:10.2f}".format(
        "Total commission:",
        total_commission_units + total_nano / NANOS_IN_ONE
    ))

    item_store.dump()


def main():
    parser = argparse.ArgumentParser(description="Tinkoff Investments Tool")
    parser.add_argument("-d", "--days", type=int, help="Days ago to count from", default=30)
    args = parser.parse_args()

    with Client(_TOKEN) as client:
        calculate_total_profit(client, days=args.days, verbose_level=1)


if __name__ == "__main__":
    main()
