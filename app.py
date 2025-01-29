import json

from flask import Flask

from lab13.lab13 import lab_13
from lab14.lab14 import lab_14
from poll_params import poll_params
# Импортируем планировщик
import scheduler

app = Flask(__name__)
app.register_blueprint(lab_13)
app.register_blueprint(lab_14)
app.register_blueprint(poll_params)
with open('modbusRESTAPI/config.json') as f:
    d = json.load(f)

if __name__ == "__main__":
    app.run(debug=False, port=d["port"])
