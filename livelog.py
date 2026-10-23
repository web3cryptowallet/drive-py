# READ AND WRITE HIERARCHICAL LIVELOG RECORDS [
class LiveLog:
    # INITIALIZE LIVE LOG [
    def __init__(self, filename):
        self.file = open(filename, "w")
    # INITIALIZE LIVE LOG ]
    # OPEN A NESTED LIVELOG BLOCK [
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
    # OPEN A NESTED LIVELOG BLOCK ]
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END [
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
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END ]
    # BEGIN SUBS FOR LIVE LOG [
    def begin_subs(self, path):
        self.begin(path.split('/'))
    # BEGIN SUBS FOR LIVE LOG ]
    # END SUBS FOR LIVE LOG [
    def end_subs(self, path):
        self.end(path.split('/'))
    # END SUBS FOR LIVE LOG ]
    # WRITE A LIVELOG RECORD OR STORED VALUE [
    def put(self, s):
        if self.path is None:
            return

        if self.empty: # Empty optimization
            self.file.write("# " + self.path + " [\n")
            self.empty = False

        self.file.write(s + '\n')
    # WRITE A LIVELOG RECORD OR STORED VALUE ]
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES [
    def flush(self):
        self.file.flush()
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES ]
# READ AND WRITE HIERARCHICAL LIVELOG RECORDS ]


