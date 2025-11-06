import asyncio

class WrapperAsync:
    def __init__(self, wrapper):
        self.wrapper = wrapper

    class PredictProxy:
        def __init__(self, wrapper):
            self.wrapper = wrapper

        async def async_run(self, X):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.wrapper.predict, X)

    class PredictProbaProxy:
        def __init__(self, wrapper):
            self.wrapper = wrapper

        async def async_run(self, X):
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self.wrapper.predict_proba, X)

    @property
    def predict(self):
        return self.PredictProxy(self.wrapper)

    @property
    def predict_proba(self):
        return self.PredictProbaProxy(self.wrapper)
