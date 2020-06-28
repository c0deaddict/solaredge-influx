import argparse
import requests
from os import getenv
import sys

from influxdb import InfluxDBClient
from datetime import datetime, timedelta


solaredge_api_url = "https://monitoringapi.solaredge.com"
required_version = dict(release="1.0.0")


def api_request(api_key, path, params=dict()):
    params = dict(**params, api_key=api_key)
    response = requests.get(solaredge_api_url + path, params, timeout=60)
    if response.status_code != 200:
        raise Exception(f"Solaredge API error {response.status_code}")
    return response.json()


def version_check(args, influx):
    current = api_request(args.api_key, "/version/current")["version"]
    supported = api_request(args.api_key, "/version/supported")["supported"]
    print(f"Solaredge API version: {current}")
    if required_version not in supported:
        print(f"API version {required_version} is NOT supported anymore")
        sys.exit(1)
    else:
        print("API version is supported")


def show_inventory(args, influx):
    response = api_request(args.api_key, f"/site/{args.site_id}/inventory")
    for inv in response["Inventory"]["inverters"]:
        print(inv["name"])
        print(f"Model: {inv['manufacturer']} {inv['model']}")
        print(f"Serial number: {inv['SN']}")
        print(f"Firmware version (CPU): {inv['cpuVersion']}")
        print(f"Connected optimizers: {inv['connectedOptimizers']}")


def add_time_period_args(parser):
    parser.add_argument(
        "--start",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
        help="Start time in format YYYY-MM-DD hh:mm:ss",
        default=None,
    )
    parser.add_argument(
        "--end",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M:%S"),
        help="End time in format YYYY-MM-DD hh:mm:ss",
        default=None,
    )
    parser.add_argument(
        "--minutes",
        type=int,
        help="Time period in minutes. Can be used with --start or --end",
    )


def time_period_params(args, max_period):
    if args.start and args.end:
        if args.minutes:
            print("Start, end and minutes are given, pick two.")
            sys.exit(1)
    else:
        if not args.minutes:
            print("Missing the minutes period.")
            sys.exit(1)
        if args.start:
            args.end = args.start + timedelta(minutes=args.minutes)
        elif args.end:
            args.start = args.end - timedelta(minutes=args.minutes)
        else:
            args.end = datetime.now().replace(microsecond=0)
            args.start = args.end - timedelta(minutes=args.minutes)

    if args.end - args.start > max_period:
        print(f"Time period exceeds maximum {max_period}")
        sys.exit(1)

    return dict(
        startTime=args.start.strftime("%Y-%m-%d %H:%M:%S"),
        endTime=args.end.strftime("%Y-%m-%d %H:%M:%S"),
    )


def convert_inverter_metric(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")

    fields = dict(
        totalActivePower=metric["totalActivePower"],
        dcVoltage=metric["dcVoltage"],
        powerLimit=metric["powerLimit"],
        totalEnergy=metric["totalEnergy"],
        temperature=metric["temperature"],
        operationMode=metric["operationMode"],
        acCurrent=metric["L1Data"]["acCurrent"],
        acVoltage=metric["L1Data"]["acVoltage"],
        acFrequency=metric["L1Data"]["acFrequency"],
        apparentPower=metric["L1Data"]["apparentPower"],
        activePower=metric["L1Data"]["activePower"],
        reactivePower=metric["L1Data"]["reactivePower"],
        cosPhi=metric["L1Data"]["cosPhi"],
    )

    # Not present when inverterMode="SLEEPING"
    if "groundFaultResistance" in metric:
        fields["groundFaultResistance"] = metric["groundFaultResistance"]

    return dict(
        measurement="solaredge_inverter",
        tags=tags,
        time=time.astimezone().isoformat(),
        fields=fields,
    )


def import_inverter_data(args, influx):
    params = time_period_params(args, timedelta(days=7))
    url = f"/equipment/{args.site_id}/{args.serial}/data"
    response = api_request(args.api_key, url, params)
    tags = dict(site_id=args.site_id, serial=args.serial)
    influx.write_points(
        convert_inverter_metric(metric, tags)
        for metric in response["data"]["telemetries"]
    )


def convert_power_metric(metric, tags):
    time = datetime.strptime(metric["date"], "%Y-%m-%d %H:%M:%S")
    power = metric["value"]
    power = float(power if power is not None else 0)
    return dict(
        measurement="solaredge_power",
        tags=tags,
        time=time.astimezone().isoformat(),
        fields=dict(power=power),
    )


def import_power_data(args, influx):
    params = time_period_params(args, timedelta(days=30))
    response = api_request(args.api_key, f"/site/{args.site_id}/power", params)
    tags = dict(site_id=args.site_id)
    influx.write_points(
        convert_power_metric(metric, tags) for metric in response["power"]["values"]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-key",
        help="Solaredge API key (env SOLAREDGE_API_KEY)",
        default=getenv("SOLAREDGE_API_KEY"),
    )
    parser.add_argument(
        "--site-id",
        help="Site ID (env SOLAREDGE_SITE_ID)",
        default=getenv("SOLAREDGE_SITE_ID"),
    )
    parser.add_argument(
        "--influx-host",
        help="InfluxDB host, defaults to 'localhost' (env INFLUXDB_HOST)",
        default=getenv("INFLUX_HOST", "localhost"),
    )
    parser.add_argument(
        "--influx-port",
        help="InfluxDB port, defaults to 8086 (env INFLUX_PORT)",
        type=int,
        default=int(getenv("INFLUX_PORT", "8086")),
    )
    parser.add_argument(
        "--influx-db",
        help="InfluxDB database (env INFLUX_DB)",
        default=getenv("INFLUX_DB"),
    )
    subparsers = parser.add_subparsers()

    parser_version = subparsers.add_parser("version", help="version check")
    parser_version.set_defaults(func=version_check)

    parser_inventory = subparsers.add_parser("inventory", help="show inventory")
    parser_inventory.set_defaults(func=show_inventory)

    parser_import_inventory = subparsers.add_parser(
        "inverter", help="import inverter data"
    )
    parser_import_inventory.add_argument(
        "--serial", help="Inverter Serial number", required=True
    )
    add_time_period_args(parser_import_inventory)
    parser_import_inventory.set_defaults(func=import_inverter_data)

    parser_import_power = subparsers.add_parser("power", help="import power data")
    add_time_period_args(parser_import_power)
    parser_import_power.set_defaults(func=import_power_data)

    args = parser.parse_args()

    if args.api_key is None:
        print(
            "No api-key given. Either specify it via the --api-key "
            "argument of the SOLAREDGE_API_KEY environment variable"
        )

    if args.site_id is None:
        print(
            "No site-id given. Either specify it via the --site-id "
            "argument of the SOLAREDGE_SITE_ID environment variable"
        )
        sys.exit(1)

    if "func" not in args:
        parser.print_help()
        sys.exit(1)

    influx = InfluxDBClient(host=args.influx_host, port=args.influx_port)
    influx.switch_database(args.influx_db)
    influx.ping()

    args.func(args, influx)


if __name__ == "__main__":
    main()
