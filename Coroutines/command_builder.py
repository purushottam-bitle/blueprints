# --- RobotCommandBuilder Utility ---

class RobotCommandBuilder:
    def __init__(self, suite_path: str, output_dir: str):
        self.suite_path = suite_path
        self.output_dir = output_dir
        self.variables = []
        self.tags = []
        self.test_cases = []

    def add_variable(self, key: str, value: str):
        self.variables.append((key, value))

    def add_tag(self, tag: str):
        self.tags.append(tag)

    def add_test_case(self, test_name: str):
        self.test_cases.append(test_name)

    def build(self):
        cmd = ["robot"]

        for k, v in self.variables:
            cmd.extend(["-v", f"{k}:{v}"])

        for tag in self.tags:
            cmd.extend(["-i", tag])

        for test in self.test_cases:
            cmd.extend(["--test", test])

        cmd.extend(["--outputdir", self.output_dir])
        cmd.append(self.suite_path)

        return cmd

# --- PabotCommandBuilder Utility ---

class PabotCommandBuilder:
    def __init__(self, suite_path: str, output_dir: str, processes: int = 2):
        self.suite_path = suite_path
        self.output_dir = output_dir
        self.processes = processes
        self.variables = []
        self.tags = []
        self.test_cases = []

    def add_variable(self, key: str, value: str):
        self.variables.append((key, value))

    def add_tag(self, tag: str):
        self.tags.append(tag)

    def add_test_case(self, test_name: str):
        self.test_cases.append(test_name)

    def build(self):
        cmd = ["pabot", f"--processes", str(self.processes)]

        for k, v in self.variables:
            cmd.extend(["-v", f"{k}:{v}"])

        for tag in self.tags:
            cmd.extend(["-i", tag])

        for test in self.test_cases:
            cmd.extend(["--test", test])

        cmd.extend(["--outputdir", self.output_dir])
        cmd.append(self.suite_path)

        return cmd
