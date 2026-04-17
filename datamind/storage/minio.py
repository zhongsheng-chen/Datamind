from typing import Optional, List
from datamind.storage.base import StorageBackend
from datamind.storage.admin import StorageAdmin


class MinioStorage(StorageBackend, StorageAdmin):

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def save(self, key: str, data: bytes):
        self.client.put_object(
            self.bucket,
            key,
            data,
            length=len(data),
        )

    def load(self, key: str) -> bytes:
        obj = self.client.get_object(self.bucket, key)
        return obj.read()

    def delete(self, key: str):
        self.client.remove_object(self.bucket, key)

    def exists(self, key: str) -> bool:
        try:
            self.client.stat_object(self.bucket, key)
            return True
        except:
            return False

    def list(self, prefix: Optional[str] = None) -> List[str]:
        objects = self.client.list_objects(self.bucket, prefix=prefix or "", recursive=True)
        return [obj.object_name for obj in objects]

    def create_bucket(self, name: str):
        if not self.client.bucket_exists(name):
            self.client.make_bucket(name)

    def list_buckets(self) -> List[str]:
        return [b.name for b in self.client.list_buckets()]

    def ensure_bucket(self, name: str):
        if not self.client.bucket_exists(name):
            self.client.make_bucket(name)