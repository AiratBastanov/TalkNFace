"""The gate watchdog must release the real Windows venv worker, not just its stub."""
import os
import subprocess
import sys
import unittest
import psutil
from lifecycle import terminate_owned_tree


class LifecycleSafety(unittest.TestCase):
    def test_only_owned_descendants_are_terminated(self):
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        leaf = "import time; print('ready',flush=True); time.sleep(120)"
        root = ("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c'," + repr(leaf)
                + "],stdout=subprocess.PIPE,text=True,creationflags=" + str(flags)
                + "); p.stdout.readline(); print('ready',flush=True); time.sleep(120)")
        owned = subprocess.Popen([sys.executable, '-c', root], stdout=subprocess.PIPE, text=True, creationflags=flags)
        sibling = subprocess.Popen([sys.executable, '-c', leaf], stdout=subprocess.PIPE, text=True, creationflags=flags)
        try:
            self.assertEqual(owned.stdout.readline().strip(), 'ready')
            self.assertEqual(sibling.stdout.readline().strip(), 'ready')
            descendants = psutil.Process(owned.pid).children(recursive=True)
            self.assertGreaterEqual(len(descendants), 1)
            terminated = terminate_owned_tree(owned)
            self.assertIn(owned.pid, terminated)
            self.assertIsNotNone(owned.poll())
            self.assertIsNone(sibling.poll(), 'Unrelated sibling must stay alive')
            self.assertFalse(any(p.is_running() for p in descendants))
        finally:
            terminate_owned_tree(owned)
            terminate_owned_tree(sibling)
            owned.stdout.close()
            sibling.stdout.close()


if __name__ == '__main__':
    unittest.main()
