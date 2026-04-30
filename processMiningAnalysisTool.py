import pm4py
def main():
    print("The analysis tool is starting. Awaiting instructions.")
    while True:
        instruction = input()

        if instruction == "help":
            print("The current commands are: close (closes the program) \n help (shows the available commands)")

        if instruction == "close":
            print("The analysis tool will close now")
            return
        
        if instruction == "comparison":
            userContinue = "yes"
            while userContinue == "yes":
                print("please enter the file name.")
                fileName = input()
                print("do you want to load additional files? If yes type yes.")
                userContinue = input()


if __name__ == "__main__":
    main()