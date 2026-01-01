# Libraries
import random
import sys

# Variables
movie_list_length = 366  # should be the number of movies + 1

def select_random():
    """Select and display a random movie from the list"""
    movie_number = random.randrange(1, movie_list_length)
    print(f"movie number {movie_number} has been selected.")


def list_unwatched():
    """Display unwatched movies"""
    # Add your logic here
    print("Listing unwatched movies...")
    #with open('filmlist.txt', 'r') as file:
    #    print(file.read())

def list_watched():
    """Display watched movies"""
    # Add your logic here
    print("Listing watched movies...")

def show_help():
    """Display available commands"""
    with open('help.txt', 'r', encoding="utf-8") as file:
        print(file.read())

# Main program - handle command-line arguments
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: No command provided. Use --help for usage information.")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "-random":
        select_random()
    elif command == "-listunwatched":
        list_unwatched()
    elif command == "-listwatched":
        list_watched()
    elif command == "help":
        show_help()
    else:
        print(f"Error: Unknown command '{command}'")
        sys.exit(1)
