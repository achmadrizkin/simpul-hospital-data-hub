"""Minimal HL7 v2 reader for ORU^R01 lab result messages."""


def parse(message: str) -> dict:
    segments = [s for s in message.replace("\r\n", "\r").replace("\n", "\r").split("\r") if s.strip()]
    result: dict = {"msh": None, "pid": None, "obr": None, "obx": []}
    for segment in segments:
        fields = segment.split("|")
        name = fields[0]
        if name == "MSH":
            # MSH-1 is the field separator itself, so indexes shift by one.
            result["msh"] = {
                "sending_app": _get(fields, 2),
                "datetime": _get(fields, 6),
                "type": _get(fields, 8),
                "control_id": _get(fields, 9),
            }
        elif name == "PID":
            ids = {}
            for rep in _get(fields, 3).split("~"):
                comps = rep.split("^")
                if comps and comps[0]:
                    id_type = comps[4] if len(comps) > 4 else "MR"
                    ids[id_type] = comps[0]
            result["pid"] = {
                "ids": ids,
                "name": _get(fields, 5),
                "birth_date": _get(fields, 7),
                "sex": _get(fields, 8),
                "address": _get(fields, 11),
                "phone": _get(fields, 13),
            }
        elif name == "OBR":
            result["obr"] = {"order_id": _get(fields, 3), "observed_at": _get(fields, 7)}
        elif name == "OBX":
            code = _get(fields, 3).split("^")
            result["obx"].append({
                "set_id": _get(fields, 1),
                "code": code[0],
                "text": code[1] if len(code) > 1 else code[0],
                "value": _get(fields, 5),
                "unit": _get(fields, 6),
                "ref_range": _get(fields, 7),
                "flag": _get(fields, 8),
            })
    return result


def _get(fields: list[str], index: int) -> str:
    return fields[index] if len(fields) > index else ""


def hl7_datetime(value: str) -> str | None:
    if len(value) < 8:
        return None
    iso = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
    if len(value) >= 12:
        iso += f"T{value[8:10]}:{value[10:12]}:{value[12:14] or '00'}"
    return iso
