from threading import Thread
import os
import stat
import sys
import time

filename = 'com'
initial_state = 33188

writing = False

class Messenger():
	def __init__(self):
		self.filename = filename
		self.exists()
		self.initial_state = initial_state
		self.last_state = self.current_state = self.get_state()
		self.reset_perms()

	def exists(self):
		if not os.path.exists(self.filename):
			try:
				open(filename, 'w').close()
			except:
				print('Error creating communication file.')
				os._exit(1)
			print('File created.')

	def reset_perms(self):
		os.chmod(self.filename, self.initial_state)

	def _parse_bin(self, as_bin):
		perms = list(map(lambda x: int(x), as_bin))
		as_dict = {'r': perms[0], 'w': perms[1], 'x': perms[2]}
		return as_dict

	def _to_bin(self, octal):
		last_bit = oct(octal)[-1:]
		as_bin = bin(int(last_bit))
		bits = len(as_bin)-2
		as_bin = f'{(3-bits)*"0"}{as_bin[-bits:]}'
		return as_bin

	def _check_perms(self):
		file_perms = os.stat(self.filename)
		mode = file_perms.st_mode
		as_bin = self._to_bin(mode)
		return as_bin

	def get_state(self):
		state = self._check_perms()
		parsed = self._parse_bin(state)
		return parsed
	
	def push_state(self, state):
		code = (4 * int(state['r'])) + (2 * int(state['w'])) + int(state['x'])
		new_perm_oct = f'{oct(self.initial_state)[-4:-1]}{code}'
		new_perm = int(new_perm_oct, 8)
		try:
			os.chmod(self.filename, new_perm)
		except Exception as e:
			print(f'Could not set permissions: {e}')
			return False					
		return True

	def update_state(self):
		self.last_state = self.current_state
		self.current_state = self.get_state()

	def mark_as_read(self, state, was_read):
		state['r'] = int(was_read)
		self.push_state(state)


class Receiver(Messenger):
	def __init__(self, *args, **kwargs):
		super(Receiver, self).__init__(*args, **kwargs)
		self.bitstring = ''

	def interpret_state(self, state):
		if state['r'] == 1:
			return
		self.bitstring += str(state['x'])
		self.mark_as_read(state, True)

	def print_bitstring(self):
		bitstring = self.bitstring
		chars = len(bitstring) / 8
		if chars != int(chars):
			print(f'Bad bitstring: {bitstring}')
			return
		string = ''
		for i in range(int(chars)):
			ascii_val = bitstring[i*8:(i*8)+8]
			char = chr(int(ascii_val, 2))
			string += char
		print(f'\r<{string}>\n\n> ', end='')

	def end_reading(self, state):
		if state['w'] == 1:
			return
		self.interpret_state(state)
		self.print_bitstring()
		self.reset_perms()
		self.bitstring = ''

	def poll(self):
		busy = False
		while True:
			if not writing:
				if self.current_state['w'] == 1:
					if not busy:
						busy = True
						print('\rReceiving message...')
				
					self.interpret_state(self.current_state)
		
				if self.last_state['w'] == 1 and self.current_state['w'] == 0:
					self.end_reading(self.current_state)
					busy = False
			
				self.update_state()

			time.sleep(0.01)


class Sender(Messenger):
	def __init__(self, *args, **kwargs):
		super(Sender, self).__init__(*args, **kwargs)

	def _msg_to_bin(self, message):
		bin_str = ''
		for char in message:
			bin_val = bin(ord(char))
			bin_val = bin_val[-(len(bin_val)-2):]
			if len(bin_val) < 8:
				diff = 8 - len(bin_val)
				bin_val = f'{diff*"0"}{bin_val}'
			bin_str += bin_val
		return bin_str

	def disable_write(self, state):
		state['w'] = 0
		return self.push_state(state)
		

	def send_bit(self, state, bit):
		state['w'] = 1
		state['x'] = int(bit)
		state['r'] = 0
		return self.push_state(state)

	def ready_check(self):
		self.update_state()
		return self.current_state['r'] == 1

	def send_message(self, message):
		bitstring = self._msg_to_bin(message)
		iter = 0
		global writing
		writing = True
		for bit in bitstring:
			sent = False
			while not sent:
				if self.ready_check() or iter == 0:
					sent = self.send_bit(self.current_state, bit)
					iter += 1
				else:
					time.sleep(0.01)
		self.disable_write(self.current_state)
		writing = False

	def get_input(self):
		message = ''
		while True:
			message = input('> ')
			if message == 'exit':
				os._exit(0)
			if message.replace(' ','').isalnum() and message != '':
				print('Sending message...\n')
				self.send_message(message)
			else:
				print('Invalid message.')


if __name__ ==  '__main__':
	r = Receiver()
	s = Sender()
	
	Thread(target=r.poll).start()
Thread(target=s.get_input).start()
