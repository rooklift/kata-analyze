#!/usr/bin/env python3

class ParserFail(Exception):
	pass

class IllegalMove(Exception):
	pass

class ParseResult:
	def __init__(self, root, readcount):
		self.root = root
		self.readcount = readcount

# -------------------------------------------------------------------------------------------------

class Board:

	def __init__(self, width, height, state = None, ko = None, active = "b", caps_by_b = 0, caps_by_w = 0):

		self.width = width
		self.height = height
		self.state = []
		self.ko = ko
		self.active = active
		self.caps_by_b = caps_by_b
		self.caps_by_w = caps_by_w

		for x in range(width):
			self.state.append([])
			for y in range(height):
				if state:
					self.state[x].append(state[x][y])
				else:
					self.state[x].append("")


	def __eq__(self, other):
		if self.width != other.width or self.height != other.height:
			return False
		if self.ko != other.ko or self.active != other.active:
			return False
		if self.caps_by_b != other.caps_by_b or self.caps_by_w != other.caps_by_w:
			return False
		for x in range(self.width):
			for y in range(self.height):
				if self.state[x][y] != other.state[x][y]:
					return False
		return True


	def copy(self):
		return Board(self.width, self.height, self.state, self.ko, self.active, self.caps_by_b, self.caps_by_w)


	def dump(self):

		if self.ko:
			ko_x, ko_y = s_to_xy(self.ko)
		else:
			ko_x, ko_y = None, None

		for y in range(0, self.height):
			for x in range(0, self.width):
				char = "X" if self.state[x][y] == "b" else "O" if self.state[x][y] == "w" else " " if (ko_x == x and ko_y == y) else "."
				print(char, end = " ")
			print()

		print("Captures: {} by Black - {} by White".format(self.caps_by_b, self.caps_by_w))
		print("Next to play: {}".format("Black" if self.active == "b" else "White"))


	def state_at(self, s):

		x, y = s_to_xy(s)

		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			raise ValueError		# s was out of bounds

		return self.state[x][y]


	def set_at(self, s, colour):

		if colour not in ["", "b", "w"]:
			raise ValueError

		x, y = s_to_xy(s)

		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			raise ValueError		# s was out of bounds

		self.state[x][y] = colour


	def neighbours(self, s):

		x, y = s_to_xy(s)

		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			raise ValueError		# s was out of bounds

		ret = []
		if x < self.width - 1:
			ret.append(xy_to_s(x + 1, y))
		if x > 0:
			ret.append(xy_to_s(x - 1, y))
		if y < self.height - 1:
			ret.append(xy_to_s(x, y + 1))
		if y > 0:
			ret.append(xy_to_s(x, y - 1))
		return ret


	def destroy_group(self, s):

		colour = self.state_at(s)
		if not colour:
			return 0

		self.set_at(s, "")

		if colour == "b":
			self.caps_by_w += 1
		else:
			self.caps_by_b += 1

		caps = 1

		for neighbour in self.neighbours(s):
			if self.state_at(neighbour) == colour:
				caps += self.destroy_group(neighbour)

		return caps


	def has_liberties(self, s):

		if not self.state_at(s):
			return False

		touched = dict()

		return self._has_liberties_recurse(s, touched)


	def _has_liberties_recurse(self, s, touched):

		touched[s] = True

		colour = self.state_at(s)

		for neighbour in self.neighbours(s):

			if neighbour in touched:
				continue

			neighbour_colour = self.state_at(neighbour)

			if not neighbour_colour:
				return True

			if neighbour_colour == colour:
				if self._has_liberties_recurse(neighbour, touched):
					return True

		return False


	def legal_move(self, s):
		return self.legal_move_colour(s, self.active)


	def legal_move_colour(self, s, colour):		# Note: does not consider passes as "legal moves".

		assert(colour == "b" or colour == "w")

		try:
			x, y = s_to_xy(s)
		except:
			return False						# s_to_xy() can throw for many reasons, but this function has to be more tolerant.

		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			return False
		if self.state_at(s):
			return False
		if self.ko == s:
			return False

		# Move will be legal as long as it's not suicide...

		neighbours = self.neighbours(s)

		for neighbour in neighbours:
			if not self.state_at(neighbour):
				return True						# New stone has a liberty.

		opposite_colour = "b" if colour == "w" else "w"

		for neighbour in neighbours:
			if self.state_at(neighbour) == colour:
				touched = dict()
				touched[s] = True
				if self._has_liberties_recurse(neighbour, touched):
					return True					# One of the groups we're joining has a liberty other than s.
			elif self.state_at(neighbour) == opposite_colour:
				touched = dict()
				touched[s] = True
				if not self._has_liberties_recurse(neighbour, touched):
					return True					# One of the enemy groups has no liberties other than s.

		return False


	def play_move_or_pass(self, s, colour):

		assert(colour == "b" or colour == "w")

		self.ko = None
		self.active = "b" if colour == "w" else "w"

		try:
			x, y = s_to_xy(s)
		except:
			return					# s was invalid in some way; treat as a pass.

		if x < 0 or x >= self.width or y < 0 or y >= self.height:
			return					# Treat as a pass.

		self.set_at(s, colour)
		caps = 0

		for neighbour in self.neighbours(s):

			neighbour_colour = self.state_at(neighbour)

			if neighbour_colour and neighbour_colour != colour:
				if not self.has_liberties(neighbour):
					caps += self.destroy_group(neighbour)

		if not self.has_liberties(s):
			self.destroy_group(s)

		if caps == 1:
			if self._one_liberty_singleton(s):
				self.ko = self._ko_square_finder(s)


	def _one_liberty_singleton(self, s):

		colour = self.state_at(s)

		if not colour:
			return False

		liberties = 0

		for neighbour in self.neighbours(s):
			neighbour_colour = self.state_at(neighbour)
			if neighbour_colour == colour:
				return False
			if not neighbour_colour:
				liberties += 1

		return liberties == 1


	def _ko_square_finder(self, s):

		for neighbour in self.neighbours(s):
			if not self.state_at(neighbour):
				return neighbour

		return None

# -------------------------------------------------------------------------------------------------

class Node:

	def __init__(self, parent = None):

		self.parent = parent
		self.children = []
		self.props = dict()
		self._board = None

		if parent:
			parent.children.append(self)


	@property
	def width(self):

		if self._board:
			return self._board.width

		root = self.get_root()
		sz = root.get("SZ")

		if sz == None:
			return 19

		if ":" in sz:
			width_string = sz.split(":")[0]
		else:
			width_string = sz

		try:
			return min(int(width_string), 52)
		except:
			return 19


	@property
	def height(self):

		if self._board:
			return self._board.height

		root = self.get_root()
		sz = root.get("SZ")

		if sz == None:
			return 19

		if ":" in sz:
			height_string = sz.split(":")[1]
		else:
			height_string = sz

		try:
			return min(int(height_string), 52)
		except:
			return 19


	def apply(self, board):

		for s in self.all_values("AE"):
			board.set_at(s, "")

		for s in self.all_values("AB"):
			board.set_at(s, "b")
			board.active = "w"

		for s in self.all_values("AW"):
			board.set_at(s, "w")
			board.active = "b"

		for s in self.all_values("B"):
			board.play_move_or_pass(s, "b")		# Will treat s as a pass if it's not a valid move.

		for s in self.all_values("W"):
			board.play_move_or_pass(s, "w")		# Will treat s as a pass if it's not a valid move.

		pl = self.get("PL")
		if pl == "B" or pl == "b":
			board.active = "b"
		if pl == "W" or pl == "w":
			board.active = "w"


	def _cache_board(self):

		# Also caches the entire history (not doing so is silly, I guess).

		if self._board:
			return

		node = self
		history = []
		work_board = None

		while node:
			if node._board:
				work_board = node._board.copy()
				break
			else:
				history.append(node)
				node = node.parent

		history.reverse()

		if not work_board:
			work_board = Board(self.width, self.height)

		for node in history:
			node.apply(work_board)
			node._board = work_board.copy()


	def make_board(self):

		self._cache_board()
		return self._board.copy()


	def get_root(self):

		node = self
		while node.parent:
			node = node.parent
		return node


	def get_end(self):

		node = self
		while len(node.children) > 0:
			node = node.children[0]
		return node


	def history(self):

		node = self
		ret = []

		while node:
			ret.append(node)
			node = node.parent

		ret.reverse()
		return ret


	def set(self, key, value):

		key = str(key)
		value = str(value)
		self._mutor_check(key)

		self.props[key] = [value]


	def get(self, key):

		key = str(key)

		if key not in self.props:
			return ""
		return self.props[key][0]


	def has_key(self, key):
		
		return key in self.props


	def all_values(self, key):

		key = str(key)

		ret = []
		if key not in self.props:
			return ret
		for value in self.props[key]:
			ret.append(value)
		return ret


	def add_value(self, key, value):

		key = str(key)
		value = str(value)
		self._mutor_check(key)

		if key not in self.props:
			self.props[key] = []
		self.props[key].append(value)


	def add_value_fast(self, key, value):

		if key not in self.props:
			self.props[key] = []
		self.props[key].append(value)


	def delete_key(self, key):

		key = str(key)
		self._mutor_check(key)

		self.props.pop(key, None)


	def dyer(self):

		root = self.get_root()
		node = root
		dyer = {20: "??", 40: "??", 60: "??", 31: "??", 51: "??", 71: "??"}
		move_count = 0

		while True:

			s = None
			if "B" in node.props:
				s = node.props["B"][0]
			elif "W" in node.props:
				s = node.props["W"][0]

			if s != None:
				move_count += 1
				if move_count in [20, 40, 60, 31, 51, 71]:
					p = root.validated_move_string(s)
					if p:
						dyer[move_count] = p

			if len(node.children) == 0 or move_count >= 71:
				break

			node = node.children[0]

		return dyer[20] + dyer[40] + dyer[60] + dyer[31] + dyer[51] + dyer[71]


	def validated_move_string(self, s):

		# Returns s if s is an on-board SGF string, otherwise returns ""

		if not isinstance(s, str):
			return ""

		if len(s) != 2:
			return ""

		x_ascii = ord(s[0])
		y_ascii = ord(s[1])

		if x_ascii >= 97 and x_ascii <= 122:
			x = x_ascii - 97
		elif x_ascii >= 65 and x_ascii <= 90:
			x = x_ascii - 65 + 26
		else:
			return ""

		if y_ascii >= 97 and y_ascii <= 122:
			y = y_ascii - 97
		elif y_ascii >= 65 and y_ascii <= 90:
			y = y_ascii - 65 + 26
		else:
			return ""

		if x >= 0 and x < self.width and y >= 0 and y < self.height:
			return s
		else:
			return ""


	def subtree_size(self):			# Including self

		node = self
		n = 0

		while True:

			n += 1

			if len(node.children) == 0:
				return n
			elif len(node.children) == 1:
				node = node.children[0]
			else:
				for child in node.children:
					n += child.subtree_size()
				return n


	def tree_size(self):
		return self.get_root().subtree_size()


	def make_move(self, s):			# This method cannot be used for passing

		self._cache_board()

		if not self._board.legal_move(s):
			raise IllegalMove

		colourkey = self._board.active.upper()

		for node in self.children:
			if node.get(colourkey) == s:
				return node

		node = Node(self)
		node.set(colourkey, s)

		return node


	def make_pass(self):

		self._cache_board()
		colourkey = self._board.active.upper()

		for node in self.children:
			foo = node.get(colourkey);
			if foo != None:
				if self.validated_move_string(foo) == "":
					return node

		node = Node(self)
		node.set(colourkey, "")

		return node


	def _mutor_check(self, key):	# With board caches, these properties require a recursive cache clear

		if key in ["B", "W", "AB", "AW", "AE", "PL", "SZ"]:
			self._clear_board_recursive()


	def _clear_board_recursive(self):

		node = self

		while True:

			node._board = None

			if len(node.children) == 0:
				break
			elif len(node.children) == 1:
				node = node.children[0]
			else:
				for child in node.children:
					child._clear_board_recursive()
				break

# -------------------------------------------------------------------------------------------------

def s_to_xy(s):						# "cc" --> 2,2

	if not isinstance(s, str):
		raise TypeError

	if len(s) != 2:
		raise ValueError

	x_ascii = ord(s[0])
	y_ascii = ord(s[1])

	if x_ascii >= 97 and x_ascii <= 122:
		x = x_ascii - 97
	elif x_ascii >= 65 and x_ascii <= 90:
		x = x_ascii - 65 + 26
	else:
		raise ValueError

	if y_ascii >= 97 and y_ascii <= 122:
		y = y_ascii - 97
	elif y_ascii >= 65 and y_ascii <= 90:
		y = y_ascii - 65 + 26
	else:
		raise ValueError

	return (x, y)


def xy_to_s(x, y):					# 2,2 --> "cc"

	if x < 0 or x >= 52 or y < 0 or y >= 52:
		raise ValueError

	s = ""

	if x < 26:
		s += chr(x + 97)
	else:
		s += chr(x + 65 - 26)

	if y < 26:
		s += chr(y + 97)
	else:
		s += chr(y + 65 - 26)

	return s


def english_to_xy(e, height = 19, i_adjust = True):		# "Q16"     --->    15,3

	if not isinstance(e, str):
		raise TypeError

	if len(e) != 2 and len(e) != 3:
		raise ValueError

	e = e.upper()

	if e[0] not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
		raise ValueError

	x = ord(e[0]) - 65

	if i_adjust:
		if e[0] == "I":
			raise ValueError
		if x > 7:
			x -= 1

	try:
		y = height - int(e[1:])
	except:
		raise ValueError

	if y < 0 or y >= height:
		raise ValueError

	return (x, y)


def safe_string(s):     			# "safe" meaning safely escaped \ and ] characters
	s = s.replace("\\", "\\\\")
	s = s.replace("]", "\\]")
	return s


def handicap_stones(count, width, height, tygem = False):

	# From the Sabaki project by Yichuan Shen, with modifications.
	# https://github.com/SabakiHQ/go-board

	if min(width, height) <= 6 or count < 2:
		return []

	nearx = 3 if width >= 13 else 2
	neary = 3 if height >= 13 else 2
	farx = width - nearx - 1
	fary = height - neary - 1
	middlex = (width - 1) // 2
	middley = (height - 1) // 2

	if tygem:
		stones = [[nearx, fary], [farx, neary], [nearx, neary], [farx, fary]]
	else:
		stones = [[nearx, fary], [farx, neary], [farx, fary], [nearx, neary]]

	if width % 2 != 0 and height % 2 != 0 and (width >= 9 or height >= 9):

		if count == 5 or count == 7 or count >= 9:
			stones.append([middlex, middley])

		stones += [
			[nearx, middley],
			[farx, middley],
			[middlex, neary],
			[middlex, fary]
		]

	return [xy_to_s(z[0], z[1]) for z in stones[0:count]]

# -------------------------------------------------------------------------------------------------

def save(filename, node):
	root = node.get_root()
	with open(filename, "w", encoding="utf-8") as outfile:
		_write_tree(outfile, root)


def _write_tree(outfile, node):
	outfile.write("(")
	while True:
		outfile.write(";")
		for key in node.props:
			outfile.write(key)
			for value in node.props[key]:
				outfile.write("[{}]".format(safe_string(value)))
		if len(node.children) > 1:
			for child in node.children:
				_write_tree(outfile, child)
			break
		elif len(node.children) == 1:
			node = node.children[0]
			continue
		else:
			break
	outfile.write(")")
	return


def load(filename):

	# This can throw.
	# Otherwise, returns a non-empty array of roots.

	with open(filename, "rb") as infile:
		buf = infile.read()

	if filename.lower().endswith(".gib"):
		return load_gib(buf)
	elif filename.lower().endswith(".ngf"):
		return load_ngf(buf)
	else:
		return load_sgf(buf)


def load_sgf(buf):

	# Always returns at least 1 game; or throws if it cannot.

	if type(buf) is str:
		buf = bytearray(buf.encode(encoding="utf-8", errors="replace"))

	ret = []
	off = 0

	while len(buf) - off >= 3:
		try:
			o = _load_sgf_recursive(buf, off, None)
			ret.append(o.root)
			off += o.readcount
		except:
			if len(ret) > 0:
				break
			else:
				raise

	if len(ret) == 0:
		raise ParserFail("SGF load error: Found no game")

	return ret


def _load_sgf_recursive(buf, off, parent_of_local_root):

	root = None
	node = None
	tree_started = False
	inside_value = False
	escape_flag = False

	value = bytearray()
	key = bytearray()
	keycomplete = False

	i = off - 1
	while i + 1 < len(buf):

		i += 1
		c = buf[i]

		if not tree_started:
			if c <= 32:
				continue
			elif c == 40:								# (
				tree_started = True
				continue
			else:
				raise ParserFail("SGF load error: Unexpected byte before (")

		if inside_value:

			if escape_flag:
				value.append(buf[i])
				escape_flag = False
				continue
			elif c == 92:								# \
				escape_flag = True
				continue
			elif c == 93:								# ]
				inside_value = False
				if not node:
					raise ParserFail("SGF load error: Value ended by ] but node was None")
				node.add_value_fast(key.decode(encoding="utf-8", errors="replace"), value.decode(encoding="utf-8", errors="replace"))
				continue
			else:
				value.append(c)
				continue

		else:

			if c <= 32 or (c >= 97 and c <= 122):		# a-z
				continue
			elif c == 91:								# [
				if not node:
					node = Node(parent_of_local_root)
					root = node
				value = bytearray()
				inside_value = True
				keycomplete = True
				if len(key) == 0:
					raise ParserFail("SGF load error: Value started by [ but key was empty")
				if (key == b'B' or key == b'W') and ("B" in node.props or "W" in node.props):
					raise ParserFail("Multiple moves in node")
				continue
			elif c == 40:								# (
				if not node:
					raise ParserFail("SGF load error: New subtree started but node was None")
				chars_to_skip = _load_sgf_recursive(buf, i, node).readcount
				i += chars_to_skip - 1	# Subtract 1: the ( character we have read is also counted by the recurse.
				continue
			elif c == 41:								# )
				if not root:
					raise ParserFail("SGF load error: Subtree ended but local root was None")
				return ParseResult(root = root, readcount = i + 1 - off)
			elif c == 59:								# ;
				if not node:
					node = Node(parent_of_local_root)
					root = node
				else:
					node = Node(node)
				key = bytearray()
				keycomplete = False
				continue
			elif c >= 65 and c <= 90:					# A-Z
				if keycomplete:
					key = bytearray()
					keycomplete = False
				key.append(c)
				continue
			else:
				raise ParserFail("SGF load error: Unacceptable byte while expecting key")

	raise ParserFail("SGF load error: Reached end of input")


def load_ngf(buf):

	lines = [z.decode(encoding="utf-8", errors="replace").strip() for z in buf.split(b"\n")]

	if len(lines) < 12:
		raise ParserFail("NGF load error: File too short")

	# ---------------------------------------------------------------------------------------------

	try:
		boardsize = int(lines[1])
	except:
		boardsize = 19

	# ---------------------------------------------------------------------------------------------

	pw = ""
	pb = ""

	pw_fields = lines[2].split()
	pb_fields = lines[3].split()

	if len(pw_fields) > 0:
		if "�" not in pw_fields[0]:
			pw = pw_fields[0]

	if len(pb_fields) > 0:
		if "�" not in pb_fields[0]:
			pb = pb_fields[0]

	# ---------------------------------------------------------------------------------------------

	try:
		handicap = int(lines[5])
	except:
		handicap = 0

	if handicap < 0 or handicap > 9:
		raise ParserFail("NGF load error: Bad handicap")

	# ---------------------------------------------------------------------------------------------

	try:
		komi = float(lines[7])
		if komi == int(komi):
			komi += 0.5
	except:
		komi = 0

	# ---------------------------------------------------------------------------------------------

	rawdate = ""

	if len(lines[8]) >= 8:
		rawdate = lines[8][0:8]

	# ---------------------------------------------------------------------------------------------

	re = ""
	margin = ""

	result_lower = lines[10].lower()

	if "black win" in result_lower or "white los" in result_lower:
		re = "B+"
	if "white win" in result_lower or "black los" in result_lower:
		re = "W+"
	if "resign" in result_lower:
		margin = "R"
	if "time" in result_lower:
		margin = "T"

	if re != "":
		re += margin

	# ---------------------------------------------------------------------------------------------

	root = Node()
	node = root

	root.set("SZ", boardsize)
	root.set("RU", "Korean")
	root.set("KM", komi)

	if handicap > 1:
		root.set("HA", handicap)
		for s in handicap_stones(handicap, boardsize, boardsize, True):
			root.add_value("AB", s)

	if len(rawdate) == 8:
		ok = True
		for n in range(8):
			if rawdate[n] < "0" or rawdate[n] > "9":
				ok = False
		if ok:
			root.set("DT", rawdate[0:4] + "-" + rawdate[4:6] + "-" + rawdate[6:8])

	if pw:
		root.set("PW", pw)
	if pb:
		root.set("PB", pb)
	if re:
		root.set("RE", re)

	for line in lines:

		line = line.upper()

		if len(line) < 7:
			continue

		if line[0:2] == "PM":

			if line[4] == "B" or line[4] == "W":

				key = line[4]

				x = ord(line[5]) - 66
				y = ord(line[6]) - 66

				node = Node(node)

				if x >= 0 and x < boardsize and y >= 0 and y < boardsize:
					node.set(key, xy_to_s(x, y))
				else:
					node.set(key, "")		# Pass

	if len(root.children) == 0:
		raise ParserFail("NGF load error: Got no moves")

	return [root]


def load_gib(buf):

	lines = [z.decode(encoding="utf-8", errors="replace").strip() for z in buf.split(b"\n")]

	root = Node()
	node = root

	root.set("SZ", 19)								# Is this always so?
	root.set("RU", "Korean")
	root.set("KM", 0)								# Can get adjusted in a moment.

	for line in lines:

		# Game info...

		if line.startswith("\\[GAMETAG="):

			dt, re, km, pb, pw = parse_gib_gametag(line)

			if dt:
				root.set("DT", dt)
			if re:
				root.set("RE", re)
			if km:
				root.set("KM", km)

			if pb and "�" not in pb:
				root.set("PB", pb)
			if pw and "�" not in pw:
				root.set("PW", pw)

		# Split the line into tokens for the handicap and move parsing...

		fields = line.split()

		# Handicap...

		if len(fields) >= 4 and fields[0] == "INI":

			if node != root:
				raise ParserFail("GIB load error: Got INI after moves were made")

			try:
				handicap = int(fields[3])
				if handicap > 1:
					root.set("HA", handicap)
					for s in handicap_stones(handicap, 19, 19, True):
						root.add_value("AB", s)
			except:
				pass

		# Moves...

		if len(fields) >= 6 and fields[0] == "STO":

			try:
				x = int(fields[4])
				y = int(fields[5])
				key = "W" if fields[3] == "2" else "B"
				node = Node(node)
				node.set(key, xy_to_s(x, y))
			except:
				pass

	if len(root.children) == 0:
		raise ParserFail("GIB load error: got no moves")

	return [root]


def parse_gib_gametag(line):

	fields = [z.strip() for z in line.split(",")]

	dt = ""
	re = ""
	km = ""
	pb = ""
	pw = ""

	zipsu = 0

	for s in fields:

		if len(s) < 2:
			continue

		if s[0:2] == "A:":
			pw = s[2:]

		if s[0:2] == "B:":
			pb = s[2:]

		if s[0] == "C":
			dt = s[1:]
			if len(dt) > 10:
				dt = dt[0:10]
			dt = dt.replace(":", "-")

		if s[0] == "W":
			try:
				grlt = int(s[1:])
				if grlt == 0:
					re = "B+"
				elif grlt == 1:
					re = "W+"
				elif grlt == 3:
					re = "B+R"
				elif grlt == 4:
					re = "W+R"
				elif grlt == 7:
					re = "B+T"
				elif grlt == 8:
					re = "W+T"
			except:
				pass

		if s[0] == "G":
			try:
				gongje = int(s[1:])
				km = str(gongje / 10)
				if km.endswith(".0"):
					km = km[:-2]
			except:
				pass

		if s[0] == "Z":
			try:
				zipsu = int(s[1:])
			except:
				pass

	if re == "B+" or re == "W+":
		if zipsu > 0:
			re += str(zipsu / 10)

	return [dt, re, km, pb, pw]
