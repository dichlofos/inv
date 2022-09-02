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


TOKEN = open('/home/mvel/work/settings/pl/tin.txt').read().strip()


_PAPERS_BLACKLIST = {
    "МТС",
    "Газпром",
    "Детский Мир",
    # "Сбер Банк",
    "TCS Group",
    "Лензолото",
    "ПИК",
    "Роснефть",

    "Доллар США",
}

unique_names = set()


with Client(TOKEN) as client:
    accs = client.users.get_accounts()
    a = accs.accounts[0]
    # print(a.id)

    def get_request(cursor=""):
        return GetOperationsByCursorRequest(
            account_id=a.id,
            cursor=cursor,
            from_=tiu.now() - timedelta(days=90),
        )

    operations = client.operations.get_operations_by_cursor(get_request())
    total_units = 0
    total_nanos = 0

    total_commission_units = 0
    total_commission_nanos = 0

    sum_by_name_units = {}
    sum_by_name_nanos = {}

    while True:
        for item in operations.items:
            if (
                item.state != OperationState.OPERATION_STATE_CANCELED and
                item.payment.currency == "rub" and
                item.name not in _PAPERS_BLACKLIST
            ):
                if not item.name and (
                    item.type == OperationType.OPERATION_TYPE_INPUT or
                    item.type == OperationType.OPERATION_TYPE_OUTPUT or
                    item.type == OperationType.OPERATION_TYPE_TAX or
                    item.type == OperationType.OPERATION_TYPE_OVERNIGHT or
                    item.type == OperationType.OPERATION_TYPE_DIVIDEND or
                    item.type == OperationType.OPERATION_TYPE_DIVIDEND_TAX
                ):
                    continue

                if not item.name:
                    print(item)
                    assert False

                """
                if "МГТС" not in item.name:
                    continue
                """

                unique_names.add(item.name)
                """
                print(item.commission)
                print(item.payment)
                print("{}\t{}\t{}".format(item.payment.units, item.commission.units, item.name), item.type)
                print()
                """
                units = item.payment.units + item.commission.units
                nanos = item.payment.nano + item.commission.nano
                total_units += units
                total_nanos += nanos

                total_commission_units += item.commission.units
                total_commission_nanos += item.commission.nano

                if item.name not in sum_by_name_units:
                    sum_by_name_units[item.name] = 0

                if item.name not in sum_by_name_nanos:
                    sum_by_name_nanos[item.name] = 0

                sum_by_name_units[item.name] += units
                sum_by_name_nanos[item.name] += nanos

        if not operations.next_cursor:
            break

        request = get_request(cursor=operations.next_cursor)
        operations = client.operations.get_operations_by_cursor(request)

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
