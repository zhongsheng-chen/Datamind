from abc import ABC, abstractmethod
from typing import List


class StorageAdmin(ABC):

    @abstractmethod
    def create_bucket(self, name: str):
        pass

    @abstractmethod
    def list_buckets(self) -> List[str]:
        pass

    @abstractmethod
    def ensure_bucket(self, name: str):
        pass