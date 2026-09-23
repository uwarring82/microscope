"""Run from the repository root: python3 -m examples.capture"""
from pathlib import Path
from dili import Camera

with Camera() as camera:
    camera.start(exposure_lines=500, gain=40, resolution='2592x1944')
    frame = camera.read()
    Path('artifacts').mkdir(exist_ok=True)
    Path('artifacts/example.png').write_bytes(frame.png())
    Path('artifacts/example-color.png').write_bytes(frame.png('color'))
    Path('artifacts/example.raw').write_bytes(frame.pixels)
    # For fixed white balance, first capture a neutral reference and obtain
    # gains = reference.white_balance(), then use frame.png('color', gains).
    camera.stop()
