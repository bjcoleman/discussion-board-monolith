# Deploy on EC2

This document gives instruction on how to run the monolithic discussion board applicaiton on an EC2 instance. 

## One-Time Setup

The file `deploy/userdata.sh` is used in the deployment process, and you must change a line before you deploy using an EC2 instance.

* Open `deploy/userdata.sh` in Cursor or your terminal.
* Near the top of the file you will fine a line such as:

    ```
    REPO_URL="https://github.com/YOUR_GITHUB_USERNAME/discussion-board-monolith.git"
    ```
* Change `YOUR_GITHUB_USERNAME` to your Github username.
* Commit this change to the git repo, and push it back to your Github account

  ```
  git add deploy/userdata.sh
  git commit -m "set github account"
  git push origin main
  ```

If the `git push` command fails, check the url of `origin` and make sure it points at your fork of the repo

  ```
  git remote -v
  ```


## Deploy Process

The step necessary to deploy are:

* Install necessary packages
* Setup the MySQL database
* Clone the repo
* Setup the `.venv`
* Use the example `.env` file for configuration
* Create the tables
* Setup systemd services for Gunicorn
* Launch Gunicorn

The script `deploy/userdata.sh` contains all these steps, and we can tell EC2 to run these commands at launch by putting the contests of this script in the [Cloud-init](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/user-data.html#userdata-linux) which is under the userdata section of the EC2 launch wizard.

In the Launch dialog:

* (Optional) Name the instance "DiscussionBoardApp"
* Use the default `t3.micro` instance type
* Select your `vockey` for authentication
* Ensure that HTTP and SSH are enabled in the security group
* Open the "Advanced" tab, and scroll to the bottom.
* Paste the contents of `deploy/userdata.sh` into **User data**

When you launch the instance, AWS will boot it, and then run the userdata script pasted into the userdata section of the EC2 launch. This will take some time, but once it completes the applicaiton will be deployed and running. 

