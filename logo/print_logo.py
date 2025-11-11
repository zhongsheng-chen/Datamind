import pyfiglet
from datetime import datetime

logo = pyfiglet.figlet_format("Datamind")
print(logo)
print(f"Starting service at {datetime.now()}")