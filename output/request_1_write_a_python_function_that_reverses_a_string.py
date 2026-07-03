# Request #1: write a python function that reverses a string
# Completed with 2 subtask(s)

def reverse_string(s):
    """
    Reverses a given string.

    Parameters:
    s (str): The input string to be reversed.

    Returns:
    str: The reversed string.
    """
    reversed_s = ''
    for char in s:
        reversed_s = char + reversed_s
    return reversed_s

# Example usage
input_string = "Hello, World!"
reversed_string = reverse_string(input_string)
print("Original String:", input_string)
print("Reversed String:", reversed_string)
