# Anki-Youtube-Audio-Miner
This is basically how I've been studying Japanese for the last couple of months now. It's pretty cool, I think.

<strong>Introduction:</strong>

A way to combine all of these 3 packages into one thing: watching youtube, word mining and shadowing practices. Of course subs2srs already succeeded at doing so and there are other addons like Youtube Subs2srs (that I kinda stole the code design from) that did similar stuff. But because yomichan was so effective at getting words and all of it's meaning from the web, I've been exclusively using that to mine words from Youtube, though it didn't actually take the audio from the youtube video, which left me kinda clueless when I'm trying to mimic the natives' accent and manners of speaking and what not. Thus, I made this addon.


<strong>Requirements:</strong> 

Ffmpeg is a must, and it has to be callable from the terminal or command prompt.


<strong>How I use this:</strong> 

1. First I mine the words on a Youtube video by yomichan-ing the transcript (Or use whatever method works for you)

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/yomichan.gif">


2. After mining all of the words that I didn't know from the video, I go to the anki's browser and select all the cards that were edited today, open up the addon widget by going to Edit -&gt; Mine audio... (or use the short-cut key Ctrl Alt M) 

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/openmw.gif">


3. Paste the youtube link into the box, select the language of your choosing, and choose the phrase field that you want to match (I chose <strong>sentence</strong> here because it offers more context therefore less matching mistakes), and the audio field that you want add/replace.

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/setupmw.gif">


6. Press "Download" to download the audio and it's subtitles.

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/download.gif">


7. Press the "Extract sound bites" button to get the sound bites, you can also select the range of audio you want to use. Each sound bites will be added to it's matched card.

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/process1.gif">


7a. You can also select the range of audio you want to extract from, by using the slider.

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/process2.gif">


7b. If you want to extract a different range of audio, just reuse the previous downloaded audio and subtitle, change the slider and press the Extract button (If it prompts you to choose the files then just follow the gif below).

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/process3.gif">


7c. You can extract sound bites from other audio source as well by exiting the widget and open it again, then choose the mp3 and srt file, like the gif above. It's a pretty limited feature.

8. Press "Add audio" to ... add audio to the selected cards.

<img src="https://raw.githubusercontent.com/quanganhquanganh/Anki-Youtube-Audio-Miner/master/docs/addaudio.gif">


8a. If you've already extracted the bites, or want to reuse the previous ones, just push the "Add audio" button.

<a href="https://ankiweb.net/shared/info/1186808928"><strong>Ankiweb</strong></a>
