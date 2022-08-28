# Anki-Youtube-Audio-Miner

Some features that this add-on brings to Anki:
- Store Youtube videos into a personal sentence database (ala [Immersion Kit](https://immersionkit.com/)).
- Add multiple audios, sentences and screenshots into cards with related words.
- Create Subs2SRS deck, or multiple decks with a Youtube playlist.

* [How to Use](#how-to-use)
  * [Storing Youtube videos](#storing-youtube-videos)
  * [Interacting with the database](#interacting-with-the-database)
  * [Adding to related cards](#adding-to-related-cards)
  * [Creating Subs2SRS deck](#creating-subs2srs-deck)
* [Why Use This Addon](#why-use-this-addon)

# How to Use

Might take a while to get started, but it's easy.

1. Download the add-on from [AnkiWeb](https://ankiweb.net/shared/info/1186808928).
2. Install the add-on.
3. Open Anki.
4. Go to **Browse → Edit → Mine Window** (or **Ctrl+Alt+M** when inside the Browse window).
5. **If there's no runnable global ffmpeg installation**, the add-on will install it for you inside the add-on folder.
6. After that, you can now start using the add-on.

## Storing Youtube videos

1. Input the Youtube video URL (must be in the format `https://www.youtube.com/watch?v=<video_id>`, **can also be a playlist**).
2. Choose the **language** of the video.
3. Click the **"Store video"** button.
4. The video will be stored in the database, you can check it by going to the **Search tab** after it has been stored.

## Interacting with the database

1. Go to the **Search** tab. There you will see the two tables: **Subtitles** and **Videos**.
2. In the **Subtitles** tab, you can search for the subtitles by text, or by the id.
3. In the **Videos** tab, you can search for the videos by using the title, or by the id as well.
4. You can delete videos and subtitles by clicking the **"Delete"** button after **selecting the row numbers to the left of the table**.
5. You can also edit the subtitles by **double clicking** them, then click the **"Save"** button to save the changes.

## Adding to related cards

1. If you have already setup the fields in the Fields tab, **go to the 3rd step**.
2. Go to the **Fields** tab. There you will see:
  * A radio button for the **Match field**, which will be used to match the text in this field with the text in the Subtitles tab.
  * A text box for the **Sentence fields**, which will be used to add the matched text to the sentence fields in the cards.
  * A text box for the **Audio fields**, which will be used to detect the audios to download, as well as to add the audios to the cards.
  * A text box for the **Youtube fields**, which will be used to add the embeded Youtube videos to the cards.
  * A text box for the **Screenshot fields**, which will be used to detect the videos to download, as well as to add the screenshots to the cards.

  **[Note: The fields are case sensitive.]**

  **[You can add multiple fields by inserting the list of wanted fields, separated by commas.]** 

  **[Example: `Sentence1,Sentence2,Sentence3,Sentence4`]**

3. Go back to the **Download** tab.
4. **Select the cards** you want to add the matched data to in the Browse window.
5. Click the **"Add"** button, and the add-on will detect what needs to be downloaded, extracted and then add to the cards.

## Creating Subs2SRS deck

1. If you have already setup the fields in the Fields tab, **go to the 3rd step**.
2. Go to the **Fields** tab. There you will see:
  * A radio button for the **Match field**, which we **will not** use for the Subs2SRS deck.
  * A text box for the **Sentence fields**, which will be used for the sentences in the Subs2SRS deck.
  * A text box for the **Audio fields**, which will be used for the audios in the Subs2SRS deck.
  * A text box for the **Youtube fields**, which will be used for embedding the Youtube videos into the Subs2SRS deck.
  * A text box for the **Screenshot fields**, which will be used for the screenshots in the Subs2SRS deck.
  
  **[Note: The fields are case sensitive.]**
  
  **[If you added a comma separated list to the fields, only the first field will be used.]**

3. Go back to the **Download** tab.
4. Insert the **Youtube video** or **playlist URL**.
5. Choose the **language** of the video.
6. Click the **"Create deck"** button. Then the add-on will go through the same process as the "Add to related cards" feature, detect what needs to be downloaded, extracted and then make new cards to go along with the Subs2SRS deck.

# Why Use This Addon

Personally I have been using this add-on for over a year now, mostly for adding Youtube audios to the cards, but recently I started collecting videos as a new and kind-of weird hobby of mine. Very useful for my day-to-day language learning process, certainly helps making my vocabulary and grammar more interesting by adding actual real-world contexts to the cards. Here's all the merits I found while using the add-on:
  * Shadowing is all I do nowadays. Effective, quick and easy, also much less stressful than having to memorize the words by themselves.
  * Searching for the words or grammars and their uses in the database is just so much fun. Especially when you missed them in the past when watching those videos. Again, just like Immersion Kit, it brings out non-conventional contexts that you're not going to find in your average textbooks (and with Youtube rather than Anime, so many more grounded examples that you can incorporate into your daily life).
  * A way to personalize your studying, making it much more closer to your own personal style and hobbies, which helps **tremendously** with the motivation and all.

All in all, this add-on just makes language learning turn into more of a treasure hunt for me, and honestly I think I will be using this until I get like 90 years old, or something like that (I'm not sure). I hope you enjoy using it, and feel free to put up issues or suggestions on the [Github repository](https://github.com/quanganhquanganh/Anki-Youtube-Audio-Miner/issues).