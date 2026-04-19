from datamind.logging.processors import mask_sensitive

proc = mask_sensitive(mask_char="*", prefix=1, suffix=1)
# 模拟 event_dict
data = {"event": "test", "password": "my_secret_password"}
result = proc(None, None, data)

print(result["password"])
# 预期输出: m****************d