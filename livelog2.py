# WRITE NESTED LIVELOG BLOCKS [
class LiveLogBasic:
    # INITIALIZE LIVE LOG BASIC [
    def __init__(self, filename):
        self._path = ""
        self._stack = []
        self._filename = filename
    # INITIALIZE LIVE LOG BASIC ]
    # RELEASE LIVE LOG BASIC [
    def __del__(self):
        if hasattr(self, '_fs'):
            self._fs.close()
    # RELEASE LIVE LOG BASIC ]
    # OPEN NEW FOR LIVE LOG BASIC [
    def open_new(self):
        self._fs = open(self._filename, 'w', encoding='utf-8')
    # OPEN NEW FOR LIVE LOG BASIC ]

#    def get_path(self):
#        return self._stack.

    # OPEN A NESTED LIVELOG BLOCK [
    def begin(self, path):
        # Check many: list or strings
        if isinstance(path, list):
            if len(path) == 0:
                return
            self._path = path.pop()
            many = True
        else:
            self._path = path
            many = False

        self._stack.append(self._path)
        self._fs.write(f"# {self._path}[\n")
        
        if many:
            self.begin(path)
    # OPEN A NESTED LIVELOG BLOCK ]
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END [
    def end(self):
        # todo: end_subs many
        
        self._fs.write(f"# {self._path}]\n")
        self._path = ""

        if self._stack:
            self._path = self._stack.pop()
    # CLOSE A LIVELOG BLOCK OR FOLLOW THE MAP END ]
    # BEGIN SUBS FOR LIVE LOG BASIC [
    def begin_subs(self, path):
        self.begin(path.split('/'))
    # BEGIN SUBS FOR LIVE LOG BASIC ]
    # END SUBS FOR LIVE LOG BASIC [
    def end_subs(self, path):
        self.end(path.split('/'))
    # END SUBS FOR LIVE LOG BASIC ]
    # WRITE A LIVELOG RECORD OR STORED VALUE [
    def put(self, s):
        self._fs.write(f"{s}\n")
    # WRITE A LIVELOG RECORD OR STORED VALUE ]
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES [
    def flush(self):
        self._fs.flush()
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES ]
# WRITE NESTED LIVELOG BLOCKS ]
# MANAGE LCNODE FOR THE LIVELOG2 WORKFLOW [
class LCNode:
    # INITIALIZE LCNODE FOR LCNODE [
    def __init__(self, name):
        self._name = name
        self._items = {}
        self._items_index = []
        self._ss = []
    # INITIALIZE LCNODE FOR LCNODE ]
    # READ THE LIVELOG NODE NAME [
    @property
    def name(self):
        return self._name
    # READ THE LIVELOG NODE NAME ]
    # READ THE LIVELOG NODE TEXT [
    @property
    def text(self):
        return "\n".join(self._ss)
    # READ THE LIVELOG NODE TEXT ]
    # ITERATE STORED LIVELOG OR SCANNER RECORDS [
    @property
    def items(self):
        return self._items
    # ITERATE STORED LIVELOG OR SCANNER RECORDS ]
    # ITEMS INDEX FOR LCNODE [
    @property
    def items_index(self):
        return self._items_index
    # ITEMS INDEX FOR LCNODE ]
    # CLEAR LCNODE FOR LCNODE [
    def clear(self):
        for node in self._items.values():
            del node
        self._items.clear()
        self._items_index.clear()
    # CLEAR LCNODE FOR LCNODE ]
    # APPEND TEXT TO A LIVELOG PATH [
    def log(self, path, s):
        node = self.alloc_node(path, 0)
        if node:
            node.put(s)
    # APPEND TEXT TO A LIVELOG PATH ]
    # WRITE A LIVELOG RECORD OR STORED VALUE [
    def put(self, s):
        if isinstance(s, (list, tuple, set)):  # Check if list, tuple or set
            self._ss.extend(s)  # Add multiple elements
        else:
            self._ss.append(s)
    # WRITE A LIVELOG RECORD OR STORED VALUE ]
    # ALLOC NODE FOR LCNODE [
    def alloc_node(self, path, i):
        if len(path) <= i:
            return self

        name = path[i]
        if name not in self._items:
            node = LCNode(name)
            self._items[name] = node
            self._items_index.append(node)
        else:
            node = self._items[name]

        return node.alloc_node(path, i + 1)
    # ALLOC NODE FOR LCNODE ]
    # DELETE NODE FOR LCNODE [
    def delete_node(self, path):
        pass
    # DELETE NODE FOR LCNODE ]
# MANAGE LCNODE FOR THE LIVELOG2 WORKFLOW ]
# READ AND WRITE HIERARCHICAL LIVELOG RECORDS [
class LiveLog(LiveLogBasic):
    # INITIALIZE LIVE LOG [
    def __init__(self, filename):
        super().__init__(filename)
        self._tree = LCNode("LiveLog++")
        self._filename = filename
    # INITIALIZE LIVE LOG ]
    # APPEND TEXT TO A LIVELOG PATH [
    def log(self, path, s):
        if isinstance(path, str):
            vstrings = path.split('/')
        else:
            vstrings = path
        self._tree.log(vstrings, s)
    # APPEND TEXT TO A LIVELOG PATH ]
    # REPLACE FOR LIVE LOG [
    def replace(self, path, s):
        pass
    # REPLACE FOR LIVE LOG ]
    # REMOVE STORED LIVELOG CONTENT [
    def erase(self, path):
        pass
    # REMOVE STORED LIVELOG CONTENT ]
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES [
    def flush(self):
        # Clear and reopen file
        if hasattr(self, '_fs'):
            self._fs.close()
        self._fs = open(self._filename, 'w', encoding='utf-8')
        self.flush_node(self._tree)
        self._fs.flush()
    # FLUSH BUFFERED OUTPUT AND PENDING UPDATES ]
    # FLUSH NODE FOR LIVE LOG [
    def flush_node(self, node):
        if not node:
            return

        self.begin(node.name)
        self.put(node.text)

        for child in node.items_index:
            self.flush_node(child)

        self.end()
    # FLUSH NODE FOR LIVE LOG ]
    # LOAD LIVE LOG [
    def load(self):
        # Clear existing tree
        self._tree.clear()
        
        try:
            with open(self._filename, 'r', encoding='utf-8') as fs:
                node_stack = []
                current_text = []
                
                for line in fs:
                    line = line.rstrip('\n')
                    
                    # Skip empty lines
                    if not line:
                        continue

                    # Check if line is a node marker
                    if line.startswith('# '):
                        # If we have accumulated text, add it to current node
                        if current_text:
                            path = node_stack.copy()
                            self._tree.log(path, current_text)
                            current_text = []

                        # Parse node marker
                        node_name = line[2:]  # Skip "# "
                        if node_name.endswith('['):
                            # Opening tag
                            node_name = node_name[:-1].strip()  # Remove '['
                            node_stack.append(node_name)
                        elif node_name.endswith(']'):
                            # Closing tag
                            node_name = node_name[:-1].strip()  # Remove ']'
                            if node_stack:
                                node_stack.pop()
                    else:
                        # Regular text line
                        current_text.append(line)

                # Add any remaining text
                if current_text:
                    path = node_stack.copy()
                    self._tree.log(path, current_text)

        except FileNotFoundError:
            print(f"Can't open file {self._filename}")
    # LOAD LIVE LOG ]
# READ AND WRITE HIERARCHICAL LIVELOG RECORDS ]
# EXERCISE LIVELOG READ AND WRITE OPERATIONS [
def test():
    # Create a new log file
    log = LiveLog("test.log")
    log.open_new()
    
    # Test basic logging
    log.log("root", "This is a root level message")
    log.log("root/child1", "This is a child1 message")
    log.log("root/child2", "This is a child2 message")
    log.log("root/child1/grandchild", "This is a grandchild message")
    
    # Flush changes to disk
    log.flush()
    
    # Test loading
    log2 = LiveLog("test.log")
    log2.load()
    log2.log("root/child3", "This is a new message after loading")
    log2.flush()
# EXERCISE LIVELOG READ AND WRITE OPERATIONS ]
# RUN LIVELOG2 ENTRY POINT [
if __name__ == "__main__":
    test()
# RUN LIVELOG2 ENTRY POINT ]
