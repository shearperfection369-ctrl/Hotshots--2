import React, { createContext, useContext, useEffect, useRef, useState } from "react";

const MusicContext = createContext(null);

export function MusicProvider({ children }) {
  const [current, setCurrent] = useState(null); // {id, name, url, country, codec}
  const [playing, setPlaying] = useState(false);
  const [volume, setVolume] = useState(() => {
    const v = parseFloat(localStorage.getItem("tms_music_volume"));
    return Number.isFinite(v) ? v : 0.55;
  });
  const audioRef = useRef(null);

  useEffect(() => {
    if (!audioRef.current) {
      const a = new Audio();
      a.crossOrigin = "anonymous";
      a.volume = volume;
      audioRef.current = a;
      a.addEventListener("playing", () => setPlaying(true));
      a.addEventListener("pause", () => setPlaying(false));
      a.addEventListener("ended", () => setPlaying(false));
      a.addEventListener("error", () => setPlaying(false));
    }
  }, []);

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume;
    localStorage.setItem("tms_music_volume", String(volume));
  }, [volume]);

  const playStation = (station) => {
    if (!audioRef.current) return;
    if (current?.id === station.id) {
      // toggle pause
      if (audioRef.current.paused) audioRef.current.play().catch(() => {});
      else audioRef.current.pause();
      return;
    }
    setCurrent(station);
    audioRef.current.src = station.url;
    audioRef.current.play().catch(() => {});
  };

  const togglePlay = () => {
    if (!audioRef.current || !current) return;
    if (audioRef.current.paused) audioRef.current.play().catch(() => {});
    else audioRef.current.pause();
  };

  const stop = () => {
    if (audioRef.current) audioRef.current.pause();
    setCurrent(null);
    setPlaying(false);
  };

  return (
    <MusicContext.Provider value={{ current, playing, volume, setVolume, playStation, togglePlay, stop }}>
      {children}
    </MusicContext.Provider>
  );
}

export const useMusic = () => useContext(MusicContext);
