import argparse
import os
import json
import pprint
import subprocess
import logging
import time
from typing import Any, Dict, List, Union, Optional
import random

# Constants
GAEA_SWARM_EXE_PATH = r"C:\Program Files\QuadSpinner\Gaea 2\Gaea.Swarm.exe"

# Type Definitions
JSONType = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def update_all_json_key(json_obj: JSONType, key: str, new_values: List[JSONType]) -> None:
	"""
	Recursively update all instances of a key in a JSON object with new values.
	
	Args:
		json_obj: The JSON object to be updated (dict or list).
		key: The key to search for in the JSON object.
		new_values: A list of values to replace the key's value.
					If the list has a length of 1, all instances of the key will be updated to this single value.
					If the list has more than one value, the number of values must match the number of key instances in the JSON object.

	Raises:
		ValueError: If the number of new values does not match the number of occurrences of the key.
		TypeError: If there is a type mismatch between the original and new values, or if new_values is empty.
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

	Args:
		json_obj: The JSON object to search (dict or list).
		target_key: The key to search for in the JSON object.
		update_func: The function to apply to each found key's value.
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

def evaluate_vars(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluate variable assignments provided as command-line arguments.

    Args:
        args: A dictionary of command-line arguments.

    Returns:
        A dictionary of evaluated variable values.
    """
    logging.info("Starting evaluation of variable assignments.")
    vars = {}
    
    if args['vars']:
        logging.info(f"Variable assignments found: {args['vars']}")
        for var_assignment in args['vars']:
            logging.info(f"Evaluating variable assignment: {var_assignment}")
            var_name, var_expression = var_assignment.split('=')
            logging.info(f"Variable name: {var_name}, Variable expression: {var_expression}")
            if 'lambda' in var_expression:
                try:
                    logging.info(f"Evaluating lambda expression for variable '{var_name}': {var_expression}")
                    vars[var_name] = eval(var_expression)()
                    logging.info(f"Evaluated value for '{var_name}': {vars[var_name]}")
                except Exception as e:
                    logging.error(f"Error evaluating var expression: {var_expression}, {e}")
            else:
                try:
                    logging.info(f"Evaluating integer expression for variable '{var_name}': {var_expression}")
                    vars[var_name] = int(var_expression)
                    logging.info(f"Evaluated value for '{var_name}': {vars[var_name]}")
                except ValueError as e:
                    logging.error(f"Error converting var expression to int: {var_expression}, {e}")
    
    logging.info("Completed evaluation of variable assignments.")
    return vars



def configure_terrain_file(terrain_data: Dict[str, Any], output_filepath: str, vars: Dict[str, Any]) -> Dict[str, Any]:
    """
    Configure the terrain file by updating various properties and variables.

    Args:
        terrain_data: The terrain data JSON object.
        args: A dictionary of command-line arguments.
        vars: A dictionary of evaluated variable values.

    Returns:
        The updated terrain data JSON object.
    """
    logging.info("Starting configuration of terrain file.")

	# Set post build script to have @echo off 
    logging.info(f"Setting post build script to include @echo off.")
    update_all_json_key(terrain_data, 'PostBuildScript', ["@echo off"])

    # Update the Destination
    logging.info(f"Setting Destination key to {output_filepath}.")
    update_all_json_key(terrain_data, 'Destination', [output_filepath])
    
    # Update the variables in the Automation section
    def update_variable_value(json_obj: Dict[str, Any]) -> None:
        for k in json_obj.keys():
            if k in vars:
                logging.debug(f"Updating variable {k} from {json_obj[k]} to {vars[k]}.")
                json_obj[k] = str(vars[k])
    
    logging.info("Updating Variables section with evaluated variable values.")
    update_all_json_key_func(terrain_data, 'Variables', lambda obj, key: update_variable_value(obj[key]))

    def update_node_property(terrain_data: Dict[str, Any], node_id: int, property_name: str, new_value: Any) -> None:
        nodes = []
        update_all_json_key_func(terrain_data, 'Nodes', lambda obj, key: nodes.extend(obj[key].values()))
        nodes = [node for node in nodes if isinstance(node, dict)]  # filter out non-dicts
        logging.debug(f"Total nodes found: {len(nodes)}")
        for node in nodes:
            if node['Id'] == node_id:
                logging.info(f"Updating node {node_id} property {property_name} from {node.get(property_name, 'N/A')} to {new_value}.")
                node[property_name] = new_value
    
    # Propagate variable updates to corresponding nodes
    bindings = []
    logging.info("Updating node properties based on bindings.")
    update_all_json_key_func(terrain_data, 'Bindings', lambda obj, key: bindings.extend(obj[key]['$values']))
    logging.debug(f"Total bindings found: {len(bindings)}")
    for binding in bindings:
        logging.debug(f"Processing binding: {binding}")
        if binding['Variable'] in vars:
            node_id: int = binding['Node']
            property_name: str = binding['Property']
            new_value = vars[binding['Variable']]
            logging.info(f"Binding found: Updating node {node_id} property {property_name} with variable {binding['Variable']} value {new_value}.")
            update_node_property(terrain_data, node_id, property_name, new_value)

    logging.info("Configuration of terrain file completed.")
    return terrain_data

def run_gaea_build(temp_filepath: str, out_filepath: str) -> None:
    """
    Run the GAEA build process.

    Args:
        temp_filepath: The path to the temporary terrain file.
        out_filepath: The path to the output directory.
    """
    command = f'"{GAEA_SWARM_EXE_PATH}" -filename "{os.path.abspath(temp_filepath)}"'
    logging.info(f"Executing command: {command}")

    # Launch the command and wait for it to finish
    process = subprocess.Popen(command, shell=True)
    logging.info("GAEA build process started, waiting for it to complete...")
    process.wait()  # Wait for the subprocess to complete
    logging.info("GAEA build process completed.")

    report_file = os.path.join(out_filepath, "report.txt")
    logging.info(f"Looking for report.txt at: {report_file}")

    # Check for the presence of report.txt
    if os.path.exists(report_file):
        logging.info("report.txt found.")
    else:
        logging.warning("report.txt not found.")

    logging.info("GAEA build process completed successfully.")
 
def main(args: Dict[str, Any]):
	"""
	Main function to orchestrate the terrain file configuration and GAEA build process.

	Args:
		args: A dictionary of command-line arguments.
	"""

	# Load the original .terrain file (a json)
	with open(args['terrain_filepath'], 'r') as f:
		original_terrain_json = json.load(f)
	
	for i in range(args['num_runs']):
     
		output_filepath = os.path.abspath(args['output_filepath'])
		if args['increment_filepath']:
			base_output_dir = output_filepath
			
			if not os.path.exists(base_output_dir):
				os.makedirs(base_output_dir, exist_ok=True)
			
			existing_dirs = [d for d in os.listdir(base_output_dir) if os.path.isdir(os.path.join(base_output_dir, d)) and d.isdigit()]
			existing_dirs.sort()
			if existing_dirs:
				new_dir_number = int(existing_dirs[-1]) + 1
			else:
				new_dir_number = 1
			new_output_dir = os.path.join(base_output_dir, f"{new_dir_number:03d}")
			output_filepath = new_output_dir
			print(new_output_dir)
			os.makedirs(new_output_dir, exist_ok=True)
   
		vars = evaluate_vars(args)
		modified_terrain_json = configure_terrain_file(original_terrain_json.copy(), output_filepath, vars)
		
		# Save a copy to /current directory/temp/temp_(original terrain name).terrain
		temp_filename = f"temp_{os.path.basename(args['terrain_filepath'])}"
		temp_dir = os.path.join(output_filepath, 'temp')
		temp_filepath = os.path.join(temp_dir, temp_filename)
		
		os.makedirs(temp_dir, exist_ok=True)
		with open(temp_filepath, 'w') as temp_file:
			json.dump(modified_terrain_json, temp_file, indent=2)

		# Run the GAEA build process
		run_gaea_build(temp_filepath, output_filepath)
  
		# Clean up temp file
		# os.remove(temp_filepath)

def validate_args(args: Dict[str, Any]) -> bool:
	"""
	Validate the command-line arguments.

	Args:
		args: A dictionary of command-line arguments.

	Returns:
		True if all arguments are valid, False otherwise.
	"""
	if not os.path.isfile(args["terrain_filepath"]):
		logging.error(f"Error: The terrain file '{args['terrain_filepath']}' does not exist.")
		return False

	if not args['output_filepath']:
		return False
  	
	if args["num_runs"] <= 0:
		logging.error(f"Error: Number of runs {args['num_runs']} must be greater than 0")
		return False

	#TODO
	# if args["build_resolution"] & (args["build_resolution"] - 1) != 0 or args["build_resolution"] < 512:
	# 	logging.error(f"Error: The build resolution '{args['build_resolution']}' is not a valid power of two starting from 512.")
	# 	return False

	# if args["output_type"] == 'CroppedTiles':
	# 	if args["tile_size"] is None:
	# 		logging.error("Error: tile_size is required when output_type is CroppedTiles.")
	# 		return False
	# 	if args["tile_size"] < 256 or args["tile_size"] > args["build_resolution"] // 2 or (args["tile_size"] & (args["tile_size"] - 1)) != 0:
	# 		logging.error(f"Error: The tile size '{args['tile_size']}' must be a power of two starting from 256 up to half of the build resolution ({args['build_resolution'] // 2}).")
	# 		return False

	return True

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Automate GAEA build process")
	parser.add_argument("terrain_filepath", type=str, nargs='?', default='.', help="The path to the .terrain file (default: .)")
	parser.add_argument("output_filepath", type=str, nargs='?', default=".", help="The path to the output file(s) (default: .)")
	parser.add_argument('num_runs', type=int, help='The number of build runs to perform. Vars will be reevaluated per run.')
	parser.add_argument('-increment_filepath', action='store_true', help='Flag to increment file path names. (./001/out, ./002/out etc.)')
	
	# TODO: The way they calculate BuildDefinition values based on output resolution is unknown at the moment. Set build resolution settings in GAEA
	# parser.add_argument("build_resolution", type=int, help="The build resolution, a power of two starting from 512")
	# parser.add_argument('-output_type', dest='output_type', choices=['SingleImage', 'CroppedTiles'], default='CroppedTiles', help='The type of output (SingleImage or CroppedTiles) (default: CroppedTiles)')
	# parser.add_argument('-tile_size', type=int, help='Tile size, required if output_type is CroppedTiles. Must be a power of two starting from 256 up to half of the build resolution.')
	parser.add_argument('-var', dest='vars', action='append', help='Variable assignments in the form var_name=value or var_name=lambda: expression')

	args = parser.parse_args()

	args_dict = vars(args)  # Convert Namespace to dict

	# Validate arguments
	if not validate_args(args_dict):
		parser.error("Invalid arguments. Please check the errors above and try again.")

	main(args_dict)

