import functions as f

# will update this as I can
def main():
    service = f.get_gmail_services()

    while True:
        print("\nOptions:")
        print("1. Add filters to an existing label")
        print("2. Create a new label and filter")
        print("3. Exit")
        choice = input("Choose an option: ").strip()

        if choice == "1":
            f.add_filters_to_labels(service)
        elif choice == "2":
            f.create_new_label_pair(service)
        elif choice == "3":
            print("Exiting.")
            break
        else:
            print("Invalid option, please try again.")

if __name__ == '__main__':
    main()
