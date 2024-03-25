from sssssssssssssssss import unlocker
from utils.config import config
import utils

solvers = {
    "capsolver": (utils.captcha.Capsolver, config.capsolver_key),
}

ENABLED_SOLVERS = [
    solvers[solver.lower()][0](solvers[solver.lower()][1])
    for solver in config.allowed_captcha_solvers
    if solver.lower() in solvers
]

assert (
    ENABLED_SOLVERS
), "Please enable at least 1 captcha solver"

with open('tokens.txt', 'r') as f:
    tokens = f.read().splitlines()


unlocker.unlock_tokens(tokens, config.threads, ENABLED_SOLVERS)
