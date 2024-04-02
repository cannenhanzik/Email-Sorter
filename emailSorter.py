import functions as f


# will update this as I can
def main(sender_groups=None):
    if sender_groups is None:
        sender_groups = {}

    service = f.get_gmail_services()

    if not sender_groups:
        sender_groups = f.fetch_labels(service)

    while True:
        f.print_menu()
        choice = input("Choose an input: ").strip()

        if choice == "1":
            for label, senders in sender_groups.items():
                print(f"Label: {label}")
                print(f"Senders:")
                for sender in senders:
                    print(f"- {sender}")
        elif choice == "2":
            f.add_filters_to_labels(service)
        elif choice == "3":
            filter_id = input("Enter the ID of the filter to delete: ").strip()
            f.delete_existing_filters(service, filter_id)
        elif choice == "4":
            label_id = input("Enter the ID of the label to delete: ").strip()
            f.delete_label(service, label_id)
        elif choice == "5":
            f.create_new_label_pair(service, sender_groups)
        elif choice == "6":
            print("Exiting.")
            break
        else:
            print("Invalid option, please try again.")


if __name__ == '__main__':
    main()
# End
