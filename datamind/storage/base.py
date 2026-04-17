from abc import ABC, abstractmethod
from typing import Optional, List


class StorageBackend(ABC):

    @abstractmethod
    def save(self, key: str, data: bytes):
        pass

    @abstractmethod
    def load(self, key: str) -> bytes:
        pass

    @abstractmethod
    def delete(self, key: str):
        pass

    @abstractmethod
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def list(self, prefix: Optional[str] = None) -> List[str]:
        pass