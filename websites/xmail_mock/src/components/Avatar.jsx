import React from 'react';

// Self-contained initials avatar: a colored disc with the first initial, with the
// color deterministically hashed from the name/email. Renders instead of an <img>
// so a null avatar never shows a broken image and no external host is contacted.

const AVATAR_COLORS = [
  '#1a73e8', '#d93025', '#188038', '#e37400', '#9334e6',
  '#1967d2', '#129eaf', '#a8007f', '#7627bb', '#b06000',
  '#0b8043', '#3949ab', '#00897b', '#8e24aa', '#5f6368',
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = (hash << 5) - hash + str.charCodeAt(i);
    hash |= 0; // keep 32-bit
  }
  return Math.abs(hash);
}

const Avatar = ({ name = '', email = '', size = 40, className = '', title }) => {
  const seed = (name || email || '?').trim();
  const initial = (seed.charAt(0) || '?').toUpperCase();
  const color = AVATAR_COLORS[hashString(seed.toLowerCase()) % AVATAR_COLORS.length];
  return (
    <div
      className={`rounded-full flex items-center justify-center text-white font-medium select-none flex-shrink-0 ${className}`}
      style={{ width: size, height: size, backgroundColor: color, fontSize: Math.round(size * 0.45), lineHeight: 1 }}
      title={title || name || email || undefined}
      aria-label={name || email || undefined}
    >
      {initial}
    </div>
  );
};

export default Avatar;
