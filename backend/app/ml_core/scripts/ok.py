import os
import subprocess
import platform
import webbrowser


def main():
    url = "https://www.youtube.com"
    system = platform.system()

    try:
        if system == "Windows":
            chrome_paths = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]

            chrome_found = False
            for path in chrome_paths:
                if os.path.exists(path):
                    # --new-window flag opens a brand new Chrome window
                    subprocess.Popen([path, "--new-window", url])
                    print(f"New Chrome window opened with {url}")
                    chrome_found = True
                    break

            if not chrome_found:
                webbrowser.open_new(url)
                print(f"Opened {url} in new default browser window.")

        elif system == "Darwin":
            subprocess.Popen(["open", "-na", "Google Chrome", "--args", "--new-window", url])
            print(f"New Chrome window opened with {url}")

        else:
            subprocess.Popen(["google-chrome", "--new-window", url])
            print(f"New Chrome window opened with {url}")

    except Exception as e:
        print(f"Error: {e}")
        print("Falling back to default browser...")
        webbrowser.open_new(url)
        print(f"Opened {url} in new default browser window.")


if __name__ == "__main__":
    main()