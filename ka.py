import gofish2, subprocess, sys, threading, time

# This was just an experiment to see how fast GTP is or isn't.
# Limitations: no illegal board edits. We don't check for "?" responses.

exe_path = "C:\\Programs (self-installed)\\KataGo 1.11.0 OpenCL\\katago.exe"

args = [
	"gtp",
	"-model",
	"C:\\Users\\Owner\\Documents\\Misc\\KataGo\\kata1-b40c256-s11101799168-d2715431527.bin.gz"]

# -------------------------------------------------------------------------------------------------

def relay_pipe(pipe, output_stream):
	while True:
		b = pipe.readline()
		output_stream.write(b.decode("utf8"))

# -------------------------------------------------------------------------------------------------

class KataGo():

	def __init__(self):

		self.last_sent_msg_id = None			# Will be an int when valid
		self.last_received_msg_id = None		# Will be an int when valid
		self.first_receive_time = None

		self.p = subprocess.Popen(
			[exe_path] + args,
			stdin = subprocess.PIPE,
			stdout = subprocess.PIPE,
			stderr = subprocess.PIPE)

		# Thread to output stderr only...
		threading.Thread(target = relay_pipe, args = [self.p.stderr, sys.stderr], daemon = True).start()

	def send(self, msg):

		if self.last_sent_msg_id:
			msg_id = self.last_sent_msg_id + 1
		else:
			msg_id = 1

		msg = str(msg_id) + " " + msg.strip() + "\n"
		print("--> " + msg, end = "")
		self.p.stdin.write(msg.encode("utf8"))
		self.p.stdin.flush()

		self.last_sent_msg_id = msg_id

	def receive(self):

		msg = self.p.stdout.readline().decode("utf8").rstrip()		# It would end with \n otherwise

		if not self.first_receive_time:
			self.first_receive_time = time.monotonic()

		if msg.startswith("="):
			try:
				i = msg.index(" ")
			except:
				i = len(msg)
			self.last_received_msg_id = int(msg[1:i])

		return (self.last_received_msg_id, msg)

# -------------------------------------------------------------------------------------------------

def english(s, height):		# cc --> C17

	x, y = gofish2.s_to_xy(s)

	x_ascii = x + 65
	if x_ascii >= ord("I"):
		x_ascii += 1

	y = height - y

	return chr(x_ascii) + str(y)

# -------------------------------------------------------------------------------------------------

if len(sys.argv) < 2:
	print("Usage: {} <filename>".format(sys.argv[0]))
	sys.exit()

katago = KataGo()

node = gofish2.load(sys.argv[1])[0]
depth = 0

if node.width != node.height:
	raise ValueError

size = node.width
komi = float(node.get("KM")) if node.get("KM") else 0

katago.send(f"boardsize {size}")
katago.send(f"clear_board")
katago.send(f"komi {komi}")

while True:

	ab = node.all_values("AB")
	aw = node.all_values("AW")
	b = node.all_values("B")
	w = node.all_values("W")

	for item in ab:
		katago.send(f"play b {english(item, size)}")
	for item in aw:
		katago.send(f"play w {english(item, size)}")
	for item in b:
		katago.send(f"play b {english(item, size)}")
	for item in w:
		katago.send(f"play w {english(item, size)}")

	katago.send("kata-analyze interval 10")

	while True:

		incoming_msg_id, s = katago.receive()

		if incoming_msg_id != katago.last_sent_msg_id:
			continue

		moveinfos = s.split("info")

		totalvisits = 0
		topmove = None
		topvisits = 0

		for moveinfo in moveinfos:

			tokens = moveinfo.split(" ")

			if "visits" in tokens:
				totalvisits += int(tokens[tokens.index("visits") + 1])

			if not topmove and "move" in tokens:
				topmove = tokens[tokens.index("move") + 1]
				if "visits" in tokens:
					topvisits = int(tokens[tokens.index("visits") + 1])

		if totalvisits > 500:
			print(f"Node {depth}: total visits {totalvisits}, best move: {topmove} ({topvisits})")
			break

	if len(node.children) == 0:
		break

	node = node.children[0]
	depth += 1

katago.send("showboard")
boardtext = ""

while True:
	incoming_msg_id, s = katago.receive()
	if incoming_msg_id != katago.last_sent_msg_id:
		continue
	if s == "":
		break
	boardtext += s + "\n"

print(boardtext)

print("Time elapsed:")
print(time.monotonic() - katago.first_receive_time)
