# StoryQuest+++

---

## 🕹️ Game Title

**StoryQuest+++**

---

## 👥 Team Members

* The code appears to be the work of a **single developer**.

---

## 📝 Short Description

StoryQuest+++ is a fast-paced, top-down arcade survival shooter built with the Python Arcade library. The player battles waves of enemies across three distinct levels, earning XP to level up, and selecting permanent perks to boost their abilities.

### Game Objectives:

* **Levels 1 & 2:** Reach a score of **90** before the boss wave is cleared.
* **Level 3:** Defeat the **Giant Boss**.

---

## 🎮 Instructions/Controls

| Action | Control | Description |
| :--- | :--- | :--- |
| **Move** | **W, A, S, D** or **Arrow Keys** | Move the player character within the arena. |
| **Shoot** | **SPACE** or **Left Mouse Click** | Fire the primary weapon in the direction of the cursor. Hold to fire continuously. |
| **Melee** | **Z** | Perform a close-range melee attack on nearby enemies. |
| **Dash** | **LSHIFT** (Left Shift) | Quickly dash a short distance, granting temporary invulnerability (i-frames). |
| **Aim** | **Mouse Movement** | Aim the weapon and set the dash direction. |
| **Pause/Resume** | **ESC** | Pause or resume the game. |
| **Restart (Paused)** | **R** | Restart the current level (only when paused). |
| **Menu (Paused)** | **M** | Return to the main menu (only when paused). |

---

## 🚀 How to Run the Game

This game requires a Python environment and the **Arcade** library.

1.  **Install Arcade:** Open your terminal or command prompt and run the following command to install the required library:

    ```bash
    pip install arcade
    ```

2.  **Asset Structure:** Ensure you have an `photos` subdirectory in the same location as `main.py`. This folder must contain all the required image assets. The file structure should look like this:

    ```
    /game_folder
    ├── main.py
    └── photos/
        ├── Mattguitar(main).jpg
        ├── enemy1.png
        ├── enemy2.png
        ├── enemy3.png
        ├── boss.png
        └── backgrounds/
            ├── bluegradient.jpg
            ├── greengradient.png
            └── redgradient.png
    ```

3.  **Run the Game:** Navigate to the `/game_folder` in your terminal and execute:

    ```bash
    python main.py
    ```

---

## 🖼️ External Assets Used

All external assets are image files stored in the `photos/` directory and its subfolder.

* **Player Sprite:** `Mattguitar(main).jpg`
* **Enemy Sprites:** `enemy1.png`, `enemy2.png`, `enemy3.png`
* **Boss Sprite:** `boss.png`
* **Background Sprites (Level-specific):**
    * `backgrounds/bluegradient.jpg`
    * `backgrounds/greengradient.png`
    * `backgrounds/redgradient.png`
