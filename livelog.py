class LiveLog:
    def __init__(self, filename):
        self.file = open(filename, "w")

    def begin(self, path):
        self.path = path
        self.empty = True

    def end(self):
        if self.path is None:
            return

        if not self.empty:
            self.file.write("# " + self.path + " ]\n")

        self.path = None


    def put(self, s):
        if self.path is None:
            return

        if self.empty:
            self.file.write("# " + self.path + " [\n")
            self.empty = False

        self.file.write(s + '\n')


