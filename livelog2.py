class LiveLogBasic:
    def __init__(self, filename):
        self._path = ""
        self._stack = []
        self._filename = filename

    def __del__(self):
        if hasattr(self, '_fs'):
            self._fs.close()

    def open_new(self):
        self._fs = open(self._filename, 'w', encoding='utf-8')

    def begin(self, path):
        self._stack.append(self._path)
        self._path = path
        self._fs.write(f"# {self._path}[\n")

    def end(self):
        self._fs.write(f"# {self._path}]\n")
        self._path = ""

        if self._stack:
            self._path = self._stack.pop()

    def put(self, s):
        self._fs.write(f"{s}\n")

    def flush(self):
        self._fs.flush()


class LCNode:
    def __init__(self, name):
        self._name = name
        self._items = {}
        self._items_index = []
        self._ss = []

    @property
    def name(self):
        return self._name

    @property
    def text(self):
        return "\n".join(self._ss)

    @property
    def items(self):
        return self._items

    @property
    def items_index(self):
        return self._items_index

    def clear(self):
        for node in self._items.values():
            del node
        self._items.clear()
        self._items_index.clear()

    def log(self, path, s):
        node = self.alloc_node(path, 0)
        if node:
            node.put(s)

    def put(self, s):
        if isinstance(s, (list, tuple, set)):  # Check if list, tuple or set
            self._ss.extend(s)  # Add multiple elements
        else:
            self._ss.append(s)

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

    def delete_node(self, path):
        pass


class LiveLog(LiveLogBasic):
    def __init__(self, filename):
        super().__init__(filename)
        self._tree = LCNode("LiveLog++")
        self._filename = filename

    def log(self, path, s):
        vstrings = path.split('/')
        self._tree.log(vstrings, s)

    def replace(self, path, s):
        pass

    def erase(self, path):
        pass

    def flush(self):
        # Clear and reopen file
        self._fs.close()
        self._fs = open(self._filename, 'w', encoding='utf-8')
        self.flush_node(self._tree)
        self._fs.flush()

    def flush_node(self, node):
        if not node:
            return

        self.begin(node.name)
        self.put(node.text)

        for child in node.items_index:
            self.flush_node(child)

        self.end()

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
                    self.log(path, '\n'.join(current_text))

        except FileNotFoundError:
            pass  # File doesn't exist yet, that's okay 

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

if __name__ == "__main__":
    test() 