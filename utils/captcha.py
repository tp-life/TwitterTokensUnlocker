import requests
import time

from . import exceptions


class Capsolver:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()

    @property
    def name(self) -> str:
        return "Capsolver"

    @property
    def create_payload(self) -> dict:
        return {
            "clientKey": self.api_key,
            "task": {
                "type": "FunCaptchaTaskProxyLess",
                "websiteURL": "https://twitter.com",
                "websitePublicKey": "0152B4EB-D2DC-460A-89A1-629838B529C9",
            },
        }

    def solve_captcha(self) -> str:
        try:
            task_create = self.session.post(
                "https://api.capsolver.com/createTask",
                json=self.create_payload,
            )
            task = task_create.json()
            if task.get("errorId", 1):
                raise exceptions.TaskCreateError(
                    f"Error while creating task: {task['errorDescription']}"
                )
            task_id = task["taskId"]
            task_results_payload = {"clientKey": self.api_key, "taskId": task_id}

            get_task_results = self.session.post(
                "https://api.capsolver.com/getTaskResult",
                json=task_results_payload,
            )
            task_results = get_task_results.json()
            while task_results["status"] == "processing":
                task_results = self.session.post(
                    "https://api.capsolver.com/getTaskResult",
                    json=task_results_payload,
                ).json()
                time.sleep(2)
            if task_results["status"] == "error":
                raise exceptions.SolvingError(
                    f"Error while solving task: {task_results['errorDescription']}"
                )
            return task_results["solution"]["token"]
        except:
            ...  # stfu

