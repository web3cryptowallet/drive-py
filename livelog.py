class LiveLog:
    def __init__(self, filename):
        self.file = open(filename, "w")

    def begin(self, path):
        # Check if path is a list
        if isinstance(path, list):
            if len(path) == 0:
                return
            while path:
                self.path = path.pop(0)
                if self.path != '':
                    break
            many = True
        else:
            self.path = path
            many = False

        self.empty = True
        
        if many:
            self.empty = False
            self.file.write("# " + self.path + " [\n")
            self.begin(path)

    def end(self, path=None):
        # Check if path is a list
        if isinstance(path, list):
            if len(path) == 0:
                return
            self.path = path.pop()
            many = True
        else:
            many = False

        if self.path is None:
            return

        if not self.empty: # Empty optimization
            self.file.write("# " + self.path + " ]\n")

        self.path = None
        
        if many:
            self.end(path)

    def begin_subs(self, path):
        self.begin(path.split('/'))

    def end_subs(self, path):
        self.end(path.split('/'))

    def put(self, s):
        if self.path is None:
            return

        if self.empty: # Empty optimization
            self.file.write("# " + self.path + " [\n")
            self.empty = False

        self.file.write(s + '\n')

    def flush(self):
        self.file.flush()


