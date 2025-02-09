from libeconpod import Podcast,get_current_issue_from_db
import pandas as pd

import os
import sys

pd.set_option("display.max_rows", None)

def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <filename>")
        sys.exit(1)

    filename = sys.argv[1]

    if not os.path.isfile(filename):
        print(f"Error: {filename} is not a valid file or does not exist.")
        sys.exit(1)

    current_issue=get_current_issue_from_db(filename)
    if not isinstance(current_issue, Podcast):
            print('[!] Error: {} is not a Podcast() instance.'.format(filename))
            return

    print(f"{filename}:")
    print(current_issue)
    print('++++++++++++++++++++++++++++++++++++++++++++++++++++')
    print(pd.DataFrame((current_issue.audios))[["filename","date","length"]])


if __name__ == "__main__":
    main()
