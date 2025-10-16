class CodeFragment:
    def __init__(self, code=None, place=None, type_=None):
        self.code = code or []
        self.place = place
        self.type = type_

    def __repr__(self):
        return f"CodeFragment(place={self.place}, type={self.type}, code={self.code})"