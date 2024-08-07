import argparse
import os
import json
import random
import subprocess
import pprint
from typing import Any, Dict, List, Union

GAEA_SWARM_EXE_PATH = r'C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe'

JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]

def update_all_json_key(json_obj: JSONType, key: str, new_values: List[JSONType]) -> None:
	"""
	Recursively update all instances of a key in a JSON object.

	:param json_obj: The JSON object to be updated (dict or list).
	:param key: The key to search for in the JSON object.
	:param new_values: A list of values to replace the key's value. If the list has a length of 1,
					   all instances of the key will be updated to this single value.
					   If the list has more than one value, the number of values must match the
					   number of key instances in the JSON object.
	:return: The updated JSON object.
	:raises ValueError: If the number of new values does not match the number of occurrences of the key.
	:raises TypeError: If there is a type mismatch between the original and new values, or if new_values is empty.
	"""
	if not new_values:
		raise ValueError("new_values must contain at least one value.")
	
	def count_and_check_keys(obj: JSONType, key: str, value_sample: JSONType) -> int:
		count = 0
		if isinstance(obj, dict):
			for k, v in obj.items():
				if k == key:
					if not isinstance(v, type(value_sample)):
						raise TypeError(f"Type mismatch: Original value type {type(v)} and new value type {type(value_sample)}")
					count += 1
				count += count_and_check_keys(v, key, value_sample)
		elif isinstance(obj, list):
			for item in obj:
				count += count_and_check_keys(item, key, value_sample)
		return count

	def update_key(obj: JSONType, key: str, value_iter: iter) -> None:
		if isinstance(obj, dict):
			for k, v in obj.items():
				if k == key:
					obj[k] = next(value_iter)
				else:
					update_key(v, key, value_iter)
		elif isinstance(obj, list):
			for item in obj:
				update_key(item, key, value_iter)

	# Perform a dry run to count occurrences of the key and check types
	occurrences = count_and_check_keys(json_obj, key, new_values[0])
	
	# Handle the special case where new_values has only one item
	if len(new_values) == 1:
		new_values *= occurrences  # Repeat the single value for all occurrences

	# Check if the number of new values matches the occurrences
	if len(new_values) != occurrences:
		raise ValueError(f"Number of new values ({len(new_values)}) does not match the number of occurrences ({occurrences}) of the key '{key}'.")

	# Update the JSON object
	value_iter = iter(new_values)
	update_key(json_obj, key, value_iter)

def update_all_json_key_func(json_obj: JSONType, target_key: str, update_func) -> None:
	"""
	Recursively find all instances of a key in a JSON object and apply an update function to the parent JSON object.

	:param json_obj: The JSON object to search (dict or list).
	:param target_key: The key to search for in the JSON object.
	:param update_func: The function to apply to each found key's value.
	"""
	if isinstance(json_obj, dict):
		for k, v in json_obj.items():
			if k == target_key:
				update_func(json_obj, k)
			else:
				update_all_json_key_func(v, target_key, update_func)
	elif isinstance(json_obj, list):
		for item in json_obj:
			update_all_json_key_func(item, target_key, update_func)

'''
============================================================
============================================================
============================================================
'''

def evaluate_vars(args: Dict[str, Any]) -> Dict[str, Any]:
	vars = {}
	if args['vars']:
		for var_assignment in args['vars']:
			var_name, var_expression = var_assignment.split('=')
			if 'lambda' in var_expression:
				try:
					vars[var_name] = eval(var_expression)()
				except RuntimeError as e:
					print(f"Error evaluating var expression: {var_expression}, {e}")
			else:
				vars[var_name] = int(var_expression)
	return vars

def update_node_property(terrain_data: Dict[str, Any], node_id: int, property_name: str, new_value: Any) -> None:
	nodes = []
	update_all_json_key_func(terrain_data, 'Nodes', lambda obj, key: nodes.extend(obj[key].values()))

	for node in nodes:
		if node['Id'] == node_id:
			node[property_name] = new_value

def configure_terrain_file(terrain_data: Dict[str, Any], args: Dict[str, Any], vars: Dict[str, Any]) -> Dict[str, Any]:
	# Update the BakeResolution
	update_all_json_key(terrain_data, 'BakeResolution', [args['build_resolution']])
	
	# Update the variables in the Automation section
	def update_variable_value(json_obj) -> None:
		for k, _ in json_obj.items():
			if k in vars:
				json_obj[k] = str(vars[k])
	update_all_json_key_func(terrain_data, 'Variables', lambda obj, key: [update_variable_value(obj[key])])

	# Propagate variable updates to corresponding nodes: Find the nodes corresponding to the automation bindings, for each node find the property and update it 
	def update_property_value(json_obj, property_name, new_value) -> None:
		for k, _ in json_obj.items():
			if k == property_name:
				json_obj[k] = new_value
    
	bindings = []
	update_all_json_key_func(terrain_data, 'Bindings', lambda obj, key: bindings.extend(obj[key]['$values']))
	for binding in bindings:
		if binding['Variable'] in vars:
			node_id: str = str(binding['Node'])
			property_name: str = str(binding['Property'])
			new_value = vars[binding['Variable']]
			update_all_json_key_func(terrain_data, node_id, lambda obj, key: update_property_value(obj[key], property_name, new_value))

	return terrain_data


def main(args: Dict[str, Any]):
	# Validate arguments
	if not validate_args(args):
		return

	# Load the original .terrain file (a json)
	with open(args['terrain_filepath'], 'r') as f:
		original_terrain_json = json.load(f)
	
	for i in range(args['num_runs']):
		vars = evaluate_vars(args)
		modified_terrain_json = configure_terrain_file(original_terrain_json.copy(), args, vars)
		
		# Save a copy to /current directory/temp/temp_(original terrain name).terrain
		temp_filename = f"temp_{os.path.basename(args['terrain_filepath'])}"
		temp_filepath = os.path.join('temp', temp_filename)
		
		os.makedirs('temp', exist_ok=True)
		with open(temp_filepath, 'w') as temp_file:
			json.dump(modified_terrain_json, temp_file)

		# Run command with new filename in a new command window, wait until we see the text "finished" in the output, then close the process
		command = f'"{GAEA_SWARM_EXE_PATH}" -filename "{temp_filepath}"'
		print(f"Executing command: {command}")
		process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		
		while True:
			output = process.stdout.readline()
			if process.poll() is not None and output == b'':
				break
			if b'finished' in output:
				print(output.strip().decode())
				process.terminate()
				break

def validate_args(args: Dict[str, Any]) -> bool:
	if not os.path.isfile(args["terrain_filepath"]):
		print(f"Error: The terrain file '{args['terrain_filepath']}' does not exist.")
		return False
	
	if args["build_resolution"] & (args["build_resolution"] - 1) != 0 or args["build_resolution"] < 512:
		print(f"Error: The build resolution '{args['build_resolution']}' is not a valid power of two starting from 512.")
		return False

	if args["num_runs"] <= 0:
		print(f"Error: Number of runs {args['num_runs']} must be greater than 0")
		return False

	return True

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Automate GAEA build process")
	parser.add_argument("terrain_filepath", type=str, help="The path to the .terrain file")
	parser.add_argument("build_resolution", type=int, help="The build resolution, a power of two starting from 512")
	parser.add_argument('num_runs', type=int, help='The number of build runs to perform')
	parser.add_argument('-var', dest='vars', action='append', help='Variable assignments in the form var_name=value or var_name=lambda: expression')

	args = parser.parse_args()

	args_dict = vars(args)  # Convert Namespace to dict
	main(args_dict)
