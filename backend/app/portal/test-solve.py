from collections import Counter
from dataclasses import dataclass
from captcha import *

solver = DdddOcrCaptchaSolver()

solver.solve(open("2.png", "rb").read())