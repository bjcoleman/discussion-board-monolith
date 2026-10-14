# Local development setup

How to run this project on your laptop: Python environment, tests, MySQL server, and the web app.

## Prerequisites

- **Python 3.12 or newer**
- **MySQL Server** installed and running on '127.0.0.1:3306'

On macOS, if you use Homebrew, you can install and start MySQL with:

```bash
brew install mysql
brew services start mysql
```

Confirm the server is up:

```bash
mysqladmin ping -h 127.0.0.1 -P 3306 -u root -p
```

## 1. Open a MySQL administrative session

Try:

```bash
mysql -u root
```

If your installation requires a root password:

```bash
mysql -u root -p
```

Once connected, you should see a MySQL prompt. Run the following SQL statements there:

```bash
CREATE DATABASE discussion_board;

CREATE USER 'discussion_app'@'127.0.0.1'
IDENTIFIED BY 'replace_with_a_password';

GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, REFERENCES
ON discussion_board.*
TO 'discussion_app'@'127.0.0.1';
```

Replace replace_with_a_password with a password of your choice. The password must match the one you put in your local .env file in the next step.

These commands do the following:

- CREATE DATABASE creates a database called discussion_board.
- CREATE USER creates a separate account for your application.
- GRANT gives that account permissions to use the tables and run your development setup scripts.

Using a separate application user limits the permissions available to the Flask application. MySQL's `root` account has administrative privileges, while `discussion_app` is granted access only to the `discussion_board` database.

Exit the MySQL prompt:

```bash
EXIT;
```



## 2. Configure `.env`

From the repository root, copy the example file:

```bash
cp config/example.env .env
```

Open `.env` and replace `your_password_here` with your password.

## 3. Set up the Python environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
pip install -e .
```

Run tests:

```bash
pytest
```



## 4. Create the tables

Run:

```bash
python scripts/create_table.py
```

Expected output:

```bash
Discussion-board tables are ready.
```



## 5. Seed sample data (optional)

The app works with empty tables. Seed only if you want the sample data from `data/sample-data.sql`:

```bash
python scripts/seed.py
```

To restore the original sample dataset, run:

```bash
python scripts/seed.py --reset
```



## 6. Run the app

Run:

```bash
python -m discussion_board.app
```

Then open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your browser.

## 7. Reset to empty tables (optional)

To reset the database to have empty tables, run:

```bash
python scripts/delete_table.py
python scripts/create_table.py
```

