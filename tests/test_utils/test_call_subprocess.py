import unittest

from motioneye import utils


class CallSubprocessTest(unittest.TestCase):
    """Commands run without a shell, so a value in them stays one argument."""

    def test_an_argument_is_not_read_by_a_shell(self):
        output = utils.call_subprocess(['echo', '$(echo x); echo y'])

        self.assertEqual('$(echo x); echo y', output)

    def test_a_shell_cannot_be_asked_for(self):
        with self.assertRaises(TypeError):
            utils.call_subprocess('echo x', shell=True)  # type: ignore[call-arg]  # noqa: S604


if __name__ == '__main__':
    unittest.main()
