class NoJobsOnPageError(Exception):
    def __init__(self, message="", error_code=None):
        super().__init__(message)
        self.error_code = error_code  # You can add custom attributes if needed

    def __str__(self):
        if self.error_code:
            return f"[No jobs on page found {self.error_code}]: {self.args[0]}"
        return self.args[0]


class NotRelevantError(Exception):
    def __init__(self, message="", error_code=None):
        super().__init__(message)
        self.error_code = error_code  # You can add custom attributes if needed

    def __str__(self):
        if self.error_code:
            return f"[Error {self.error_code}]: {self.args[0]}"
        return self.args[0]


class AlreadyRetrievedError(Exception):
    def __init__(self, message="", error_code=None):
        super().__init__(message)
        self.error_code = error_code  # You can add custom attributes if needed

    def __str__(self):
        if self.error_code:
            return f"[Error {self.error_code}]: {self.args[0]}"
        return self.args[0]


class OutOfPolicyError(Exception):
    def __init__(self, message="", error_code=None):
        super().__init__(message)
        self.error_code = error_code  # You can add custom attributes if needed

    def __str__(self):
        if self.error_code:
            return f"[Error {self.error_code}]: {self.args[0]}"
        return self.args[0]
