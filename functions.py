import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/gmail.settings.sharing'
]


def load_credentials():
    creds_path = Path.home() / '.emailFilterer' / 'token.pickle'
    if creds_path.exists():
        with creds_path.open('rb') as token:
            creds = pickle.load(token)
    else:
        creds = None
    return creds, creds_path


def save_credentials(creds, creds_path):
    with creds_path.open('wb') as token:
        pickle.dump(creds, token)


def get_gmail_services():
    creds, creds_path = load_credentials()

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        save_credentials(creds, creds_path)

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
                sender_groups[label['name']] = label['id']
        return sender_groups
    except Exception as e:
        print(f'An error occurred while fetching labels: {e}')
        return {}


def create_label_if_not_exists(service, label_name):
    labels = fetch_labels(service)
    for existing_label_name, existing_label_id in labels.items():
        if existing_label_name.lower() == label_name.lower():
            print(f'Label {label_name} already exists.')
            return existing_label_id
    label_body = {
        'name': label_name,
        'labelListVisibility': 'labelShow',
        'messageListVisibility': 'show'
    }
    label = service.users().labels().create(userId='me', body=label_body).execute()
    print(f'Created label: {label["name"]}')
    return label['id']


def delete_label(service, label_id):
    try:
        service.users().labels().delete(userId='me', id=label_id).execute()
        print(f'Label {label_id} successfully deleted')
    except HttpError as error:
        print(f'An error occurred while deleting label: {error}')


def create_filter(service, criteria, action, label_id):
    filter_body = {
        'criteria': criteria,
        'action': action
    }
    try:
        existing_filter_id = get_filter_id(service, criteria.get('from'), label_id)
        if existing_filter_id is None:
            created_filter = service.users().settings().filters().create(userId='me', body=filter_body).execute()
            print(f'Filter created for {criteria["from"]}')
            return created_filter
        else:
            print(f'Filter already exists for {criteria["from"]}')
    except HttpError as error:
        print(f'An error occurred while creating filter: {error}')
        return None


def get_filter_id(service, sender, label_id):
    try:
        filters = service.users().settings().filters().list(userId='me').execute()
        for filter_ in filters.get('filters', []):
            criteria_match = 'criteria' in filter_ and filter_['criteria'].get('from') == sender
            action_match = 'action' in filter_ and label_id in filter_['action'].get('addLabelIds', [])
            if criteria_match and action_match:
                return filter_['id']
    except HttpError as err:
        print(f'An error occurred: {err}')
    return None


def delete_existing_filters(service, filter_id):
    try:
        service.users().settings().filters().delete(userId='me', id=filter_id).execute()
        print(f'Filter {filter_id} deleted')
    except HttpError as error:
        print(f'An error occurred while deleting filter: {error}')


def apply_label_to_existing(service, label_id, sender):
    # This function applies a specified label to all existing messages from a given sender
    try:
        query = f'from:{sender}'
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])
        for msg in messages:
            service.users().messages().modify(userId='me', id=msg['id'],
                                              body={'removeLabelIds': ['INBOX'], 'addLabelIds': [label_id]}).execute()
        print(f'Applied label {label_id} to existing messages from {sender}')
    except HttpError as error:
        print(f'An error occurred: {error}')


def add_filters_to_labels(service):
    labels = fetch_labels(service)
    print("Current labels in your inbox:")
    for label_name, label_id in labels.items():
        print(f"- {label_name}")

    label_name = input("Enter the label to add filters to: ").strip()
    label_id = labels.get(label_name)

    if label_id:
        print(f"Selected Label: {label_name}. Enter domains one by one (example.com). Type 'done' to finish:")
        domains = []
        while True:
            domain_input = input().strip().lower()  # Convert to lowercase for consistency
            if domain_input == 'done' or domain_input == '':
                break
            domains.append(domain_input)

        for domain in domains:
            criteria = {'from': domain}
            action = {'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}
            create_filter(service, criteria, action, label_id)
            apply_label_to_existing(service, label_id, domain)

        print("Filters and labels have been updated.")
    else:
        print("Label does not exist. Please create it first.")


def create_new_label_pair(service):
    new_label_name = input("Enter new label name: ").strip()
    label_id = create_label_if_not_exists(service, new_label_name)

    print("Enter domains one by one (example.com) for this new label. Type 'done' to finish:")
    domains = set()
    while True:
        domain_input = input().strip()
        if domain_input == 'done' or domain_input == '':
            break
        domains.add(domain_input)

    for domain in domains:
        criteria = {'from': domain}
        action = {'addLabelIds': [label_id], 'removeLabelIds': ['INBOX']}
        create_filter(service, criteria, action, label_id)
        apply_label_to_existing(service, label_id, domain)

    print(f'Created new label "{new_label_name}" and associated filters.')
