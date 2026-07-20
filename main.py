from supreme_zone.core.bootstrap import bootstrap


if __name__ == "__main__":
    result = bootstrap()
    print(f"{result.app_name} ready: {result.ready}")
