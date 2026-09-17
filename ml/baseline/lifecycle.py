"""Terminate only the process tree created by the gate's subprocess.Popen call."""
import psutil


def terminate_owned_tree(process):
    """Windows venv launchers have a real Python descendant; include that child."""
    if process.poll() is not None:
        return []
    parent = psutil.Process(process.pid)
    owned = parent.children(recursive=True) + [parent]
    # psutil Process objects retain creation identity to guard against PID reuse.
    for child in reversed(owned[:-1]):
        try:
            child.terminate()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.terminate()
    except psutil.NoSuchProcess:
        pass
    _, alive = psutil.wait_procs(owned, timeout=10)
    for child in alive:
        child.kill()
    _, alive = psutil.wait_procs(alive, timeout=10)
    if alive:
        raise RuntimeError('Gate-owned processes did not exit: ' + str([p.pid for p in alive]))
    process.wait(timeout=10)
    return [p.pid for p in owned]
