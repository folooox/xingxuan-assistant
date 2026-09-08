"""Exercise the actual threaded desktop connection flow, read-only remotely."""
import time
from main import App

app = App()
app.withdraw()
app.show('pool')
frame = app.frames['pool']
frame.connect()
deadline = time.monotonic() + 90
while time.monotonic() < deadline:
    app.update()
    if frame.rows and not frame.busy:
        break
    if not frame.busy and '失败' in frame.status_var.get():
        raise RuntimeError(frame.status_var.get())
    time.sleep(0.05)
assert frame.rows, frame.status_var.get()
print('desktop-connect-and-query-ok', len(frame.rows), frame.total)
app.destroy()
