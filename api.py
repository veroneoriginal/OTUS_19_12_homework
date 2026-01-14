# api.py

import datetime
import hashlib
import json
import logging
import uuid
from argparse import ArgumentParser
from email.message import Message
from enum import Enum
from http.server import (
    BaseHTTPRequestHandler,
    HTTPServer,
)
from typing import Any, Callable

from scoring.core import get_score, get_interests
from store import Store

store = Store()

class Gender(Enum):
    UNKNOWN = 0
    MALE = 1
    FEMALE = 2


class ErrorMessage(Enum):
    BAD_REQUEST = "Bad Request"
    FORBIDDEN = "Forbidden"
    NOT_FOUND = "Not Found"
    INVALID_REQUEST = "Invalid Request"
    INTERNAL_ERROR = "Internal Server Error"


SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"

OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500

ERRORS = {
    BAD_REQUEST: ErrorMessage.BAD_REQUEST.value,
    FORBIDDEN: ErrorMessage.FORBIDDEN.value,
    NOT_FOUND: ErrorMessage.NOT_FOUND.value,
    INVALID_REQUEST: ErrorMessage.INVALID_REQUEST.value,
    INTERNAL_ERROR: ErrorMessage.INTERNAL_ERROR.value,
}


class ValidationError(Exception):
    pass


class Field:
    def __init__(
            self,
            required: bool = False,
            nullable: bool = False,
    ):
        self.required = required
        self.nullable = nullable
        self.name = None  # имя поля в Request

    def __set_name__(self, owner, name):
        self.name = name

    def validate(self, value):
        if value is None:
            if self.required:
                raise ValidationError("field is required")
            return


class CharField(Field):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return
        if not isinstance(value, str):
            raise ValidationError("value must be a string")


class BaseRequest:
    def __init__(self, data: dict):
        self.data = data or {}
        self.errors = {}
        self._fields = collect_fields(self.__class__)

    def validate(self) -> bool:
        for name, field in self._fields.items():
            value = self.data.get(name)

            try:
                field.validate(value)
                setattr(self, name, value)
            except ValidationError as e:
                self.errors[name] = str(e)

        return not self.errors


class ArgumentsField(Field):
    pass


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return

        if "@" not in value:
            raise ValidationError("invalid email")


class PhoneField(Field):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return

        if isinstance(value, int):
            value = str(value)

        if not isinstance(value, str):
            raise ValidationError("phone must be string or int")

        if len(value) != 11 or not value.startswith("7"):
            raise ValidationError("invalid phone")


class DateField(Field):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return

        if not isinstance(value, str):
            raise ValidationError("date must be string")

        try:
            datetime.datetime.strptime(value, "%d.%m.%Y")
        except ValueError:
            raise ValidationError("invalid date format")


class BirthDayField(DateField):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return

        try:
            birthday = datetime.datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValidationError("invalid birthday format")

        today = datetime.date.today()
        age = (today - birthday).days // 365

        if age > 70:
            raise ValidationError("invalid birthday")


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is None:
            return

        if not isinstance(value, int):
            raise ValidationError("gender must be int")

        if value not in (0, 1, 2):
            raise ValidationError("invalid gender")


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list) or not value:
            raise ValidationError("client_ids must be non-empty list")

        for cid in value:
            if not isinstance(cid, int):
                raise ValidationError("client_ids must contain ints")


class ClientsInterestsRequest(BaseRequest):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)

class OnlineScoreRequest(BaseRequest):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

class MethodRequest(BaseRequest):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self) -> bool:
        return self.login == ADMIN_LOGIN


def check_auth(request: MethodRequest) -> bool:
    if request.is_admin:
        digest = hashlib.sha512(
            (datetime.datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT).encode("utf-8")
        ).hexdigest()
    else:
        digest = hashlib.sha512(
            ((request.account or "") + request.login + SALT).encode("utf-8")
        ).hexdigest()
    return digest == request.token


def collect_fields(cls):
    fields = {}
    for attr_name, attr_value in cls.__dict__.items():
        if isinstance(attr_value, Field):
            fields[attr_name] = attr_value
    return fields


def method_handler(
        request: dict[str, Any],
        ctx: dict[str, Any],
        settings: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], int]:
    if not isinstance(request, dict):
        return {"error": "Invalid request"}, INVALID_REQUEST

    body = request.get("body")
    if not isinstance(body, dict):
        return {"error": "Invalid request"}, INVALID_REQUEST

    method_request = MethodRequest(body)
    if not method_request.validate():
        return method_request.errors, INVALID_REQUEST

    if not check_auth(method_request):
        return ErrorMessage.FORBIDDEN.value, FORBIDDEN

    method = method_request.method

    if method == "online_score":
        arguments = method_request.arguments
        if not isinstance(arguments, dict):
            return {"error": "Invalid arguments"}, INVALID_REQUEST

        score_request = OnlineScoreRequest(arguments)
        if not score_request.validate():
            return score_request.errors, INVALID_REQUEST

        pairs = (
            (score_request.phone, score_request.email),
            (score_request.first_name, score_request.last_name),
            (score_request.gender, score_request.birthday),
        )

        def filled(x):
            return x is not None

        if not any(filled(a) and filled(b) for a, b in pairs):
            return {"error": "Invalid arguments"}, INVALID_REQUEST

        ctx["has"] = [k for k, v in arguments.items() if v is not None]

        if method_request.is_admin:
            return {"score": 42}, OK

        score = get_score(
            phone=score_request.phone,
            email=score_request.email,
            birthday=score_request.birthday,
            gender=score_request.gender,
            first_name=score_request.first_name,
            last_name=score_request.last_name,
        )

        return {"score": score}, OK

    if method == "clients_interests":
        arguments = method_request.arguments
        if not isinstance(arguments, dict):
            return {"error": "Invalid arguments"}, INVALID_REQUEST

        req = ClientsInterestsRequest(arguments)
        if not req.validate():
            return req.errors, INVALID_REQUEST

        ctx["nclients"] = len(req.client_ids)

        result = {
            str(cid): get_interests(cid)
            for cid in req.client_ids
        }

        return result, OK

    return {"error": "Invalid request"}, INVALID_REQUEST


class MainHTTPHandler(BaseHTTPRequestHandler):
    router: dict[str, Callable] = {"method": method_handler}

    def get_request_id(self, headers: Message) -> str:
        return headers.get("HTTP_X_REQUEST_ID", uuid.uuid4().hex)

    def do_POST(self) -> None:
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers["Content-Length"]))
            request = json.loads(data_string)
        except Exception:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers},
                        context,
                    )
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r).encode("utf-8"))


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", action="store", type=int, default=8080)
    parser.add_argument("-l", "--log", action="store", default=None)
    args = parser.parse_args()

    logging.basicConfig(
        filename=args.log,
        level=logging.INFO,
        format="[%(asctime)s] %(levelname).1s %(message)s",
        datefmt="%Y.%m.%d %H:%M:%S",
    )

    server = HTTPServer(("localhost", args.port), MainHTTPHandler)

    logging.info("Starting server at %s" % args.port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

    server.server_close()
