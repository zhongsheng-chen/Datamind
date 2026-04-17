from datamind.storage import get_storage


def main():
    storage = get_storage()

    print("👉 SAVE")
    key = storage.save("modelA", "model.pkl", b"hello world")
    print("key =", key)

    print("👉 LOAD")
    print(storage.load("modelA", "model.pkl"))

    print("👉 LIST")
    print(storage.list("modelA"))

    print("👉 DELETE")
    storage.delete("modelA", "model.pkl")


if __name__ == "__main__":
    main()