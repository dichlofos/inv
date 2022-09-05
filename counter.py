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

# from google.protobuf.timestamp_pb2 import Timestamp


import utils as u

_TOKEN = open(".token.txt").read().strip()
_PAPERS_BLACKLIST = u.tokenize_file("papers_blacklist.ini", ignore_comments=True)

unique_names = set()


def calculate_total_profit(client, days=30, verbose_level=0):
    print("Days ago to count from: {}".format(days))

    accs = client.users.get_accounts()
    a = accs.accounts[0]
    # print(a.id)

    def get_request(cursor=""):
        return GetOperationsByCursorRequest(
            account_id=a.id,
            cursor=cursor,
            from_=tiu.now() - timedelta(days=days),
        )

    operations = client.operations.get_operations_by_cursor(get_request())
    total_units = 0
    total_nanos = 0

    total_commission_units = 0
    total_commission_nanos = 0

    sum_by_name_units = {}
    sum_by_name_nanos = {}

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

            if not name:
                print(item)
                assert False

            unique_names.add(name)

            units = item.payment.units + item.commission.units
            nanos = item.payment.nano + item.commission.nano
            total_units += units
            total_nanos += nanos

            total_commission_units += item.commission.units
            total_commission_nanos += item.commission.nano

            if name not in sum_by_name_units:
                sum_by_name_units[name] = 0

            if name not in sum_by_name_nanos:
                sum_by_name_nanos[name] = 0

            sum_by_name_units[name] += units
            sum_by_name_nanos[name] += nanos

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
        total_commission_units + total_nanos / 1_000_000_000
    ))


def main():
    parser = argparse.ArgumentParser(description="Tinkoff Investments Tool")
    parser.add_argument("-d", "--days", type=int, help="Days ago to count from", default=30)
    args = parser.parse_args()

    with Client(_TOKEN) as client:
        calculate_total_profit(client, days=args.days, verbose_level=1)


if __name__ == "__main__":
    main()
