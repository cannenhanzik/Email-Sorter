import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import emailSorter as es

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/gmail.settings.sharing'
]


def get_gmail_services():
    home_dir = Path.home()
    hidden_dir = home_dir / '.emailFilterer'
    creds_path = hidden_dir / 'token.pickle'
    creds = None

    if creds_path.exists():
        with open(creds_path, 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open(creds_path, 'wb') as token:
            pickle.dump(creds, token)

    return build('gmail', 'v1', credentials=creds)


def fetch_labels(service):
    try:
        response = service.users().labels().list(userId='me').execute()
        labels = response.get('labels', [])
        sender_groups = {}
        for label in labels:
            if label['name'] not in ['CHAT', 'SENT', 'INBOX', 'IMPORTANT', 'DRAFT', 'SPAM',
                                     'CATEGORY_FORUMS', 'CATEGORY_UPDATES', 'CATEGORY_PERSONAL',
                                     'CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL', 'STARRED', 'UNREAD',
                                     '[Imap]/Drafts']:
                label_id = label['id']
                senders = fetch_senders_for_label(service, label_id)
                sender_groups[label['name']] = senders
        return sender_groups
    except Exception as e:
        print(f'An error occurred while fetching labels: {e}')
        return {}


def create_label(service, label_name):
    try:
        label = {'name': label_name}
        created_label = service.users().labels().create(userId='me', body=label).execute()
        print(f'Created label: {created_label["name"]}')
        return created_label
    except HttpError as error:
        print(f'An error occurred while creating label: {error}')
        return None


def delete_label(service, label_id):
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        print(f'{label_id} successfully deleted')
    except HttpError as error:
        print(f'An error occurred while deleting label: {error}')


def create_filter(service, criteria, action):
    try:
        action['removeLabelIds'] = ['INBOX']
        new_filter = {
            'criteria': criteria,
            'action': action
        }
        created_filter = service.users().settings().filters().create(userId='me', body=new_filter).execute()
        print('Filter created!')
        return created_filter
    except HttpError as error:
        print(f'An error occurred while creating filter: {error}')
        return None


def delete_filter(service, filter_id):
    try:
        service.users().settings().filters().delete(userId='me', id=filter_id).execute()
        print(f'{filter_id} successfully deleted')
    except HttpError as error:
        print(f'An error occurred while deleting {filter_id}: {error}')


def fetch_senders_for_label(service, label_id):
    try:
        messages = service.users().messages().list(userId='me', labelIds=[label_id]).execute().get('messages', [])
        domains = set()
        for message in messages:
            message_details = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = message_details.get('payload', {}).get('headers', [])
            from_header = next((header['value'] for header in headers if header['name'].lower() == 'from'), None)
            if from_header:
                from_email = from_header.split('<')[-1].split('>')[0]
                domain_name = from_email.split('@')[-1]
                domains.add('@' + domain_name)
        return domains
    except HttpError as error:
        print(f'An error occurred: {error}')
        return set()


def print_menu():
    print("\nOptions:")
    print("1. Show current labels and associated filters")
    print("2. Add filters to an existing label")
    print("3: Delete filters from an existing label")
    print("4. Delete an existing label and its filters")
    print("5: Create a new label and filter")
    print("6. Exit")


def get_label_id(service, input_label_name):
    try:
        labels_response = service.users().labels().list(userId='me').execute()
        for label in labels_response.get('label', []):
            if label['name'].lower() == input_label_name.lower():
                return label['id']
    except HttpError as error:
        print(f'An error occurred: {error}')
    return None


def get_filter_id(service, sender, label_id):
    try:
        filters = service.users().settings().filters().list(userId='me').execute()
        for FILTER in filters.get('filters', []):
            criteria_match = 'criteria' in FILTER and FILTER['criteria'].get('from') == sender
            action_match = 'action' in FILTER and label_id in FILTER['action'].get('addLabelIds', [])

            if criteria_match and action_match:
                return FILTER['id']
    except HttpError as err:
        print(f'An error occurred: {err}')
    return None


def filter_exists(service, sender, label_id):
    return get_filter_id(service, sender, label_id) is not None


def get_or_create_label(service, label_name):
    existing_labels = fetch_labels(service)

    for existing_label_name, existing_label_id in existing_labels.items():
        if existing_label_name.lower() == label_name.lower():
            return existing_label_id

        label_body = {
            'name': label_name,
            'labelListVisibility': 'labelShow',
            'messageListVisibility': 'show'
        }
        label = service.users().labels().create(userId='me', body=label_body).execute()
        print(f'Created label: {label["name"]}')
        return label['id']


def apply_label_to_existing(service, label_id, senders):
    for sender in senders:
        query = f'from:{sender}'
        response = service.users().messages().list(userId='me', q=query).execute()
        if 'messages' in response:
            messages = response['messages']
            for msg in messages:
                service.users().messages().modify(userId='me', id=msg['id'], body={'removeLabelIds': ['INBOX'],
                                                                                   'addLabelIds': [label_id]}).execute()
                print(f'Added label to existing messages from {sender}')


def delete_existing_filters(service, filter_id):
    try:
        service.users().settings().filters().delete(userId='me', id=filter_id).execute()
        print(f'Deleted {filter_id}')
    except HttpError as error:
        print(f'An error occurred: {error}')


def add_filters_to_labels(service):
    print("Current labels in your inbox:")
    labels_response = service.users().labels().list(userId='me').execute()
    excluded_labels = ['CHAT', 'SENT', 'INBOX', 'IMPORTANT', 'DRAFT', 'SPAM',
                       'CATEGORY_FORUMS', 'CATEGORY_UPDATES', 'CATEGORY_PERSONAL',
                       'CATEGORY_PROMOTIONS', 'CATEGORY_SOCIAL', 'STARRED', 'UNREAD', '[Imap]/Drafts']

    for label in labels_response.get('labels', []):
        if label['name'] not in excluded_labels:
            print(f"- {label['name']}")

    label_name = input("Enter the label to add filters to: ").strip().capitalize()

    label_id = get_label_id(service, label_name)

    if label_id:
        print(f"Selected Label: {label_name}. Enter domains one by one (example.com). Type 'done' to finish:")
        while True:
            domain_input = input().strip().lower()  # No need for '@', lowercase for consistency
            if domain_input == 'done' or domain_input == '':
                break

            # Create the filter for the domain
            filter_body = {
                'criteria': {
                    'from': domain_input
                },
                'action': {
                    'addLabelIds': [label_id],
                    'removeLabelIds': ['INBOX']
                }
            }

            service.users().settings().filters().create(userId='me', body=filter_body).execute()
            print(f"Added filter for domain {domain_input} under label {label_name}.")

            # Apply the label to existing emails for this domain
            apply_label_to_existing(service, label_id, [domain_input])

        es.main()

    else:
        print("Label does not exist.")


def create_new_label_pair(service, sender_groups):
    new_label_name = input("Enter new label name: ").capitalize().strip()
    label_id = get_or_create_label(service, new_label_name)

    print("Enter domains one by one (example.com) for this new label. Type 'done' to finish:")
    domains = set()
    while True:
        domain_input = input().strip()
        if domain_input == 'done' or domain_input == '':
            break
        domains.add(domain_input)

    for domain in domains:
        create_filter(service, {'from': domain}, {'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']})
        apply_label_to_existing(service, label_id, [domain])

    print(f'Created new label for {new_label_name}.')

    es.main()
