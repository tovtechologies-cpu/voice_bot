import React from 'react';
import { Mic, MicOff } from 'lucide-react';

const MicButton = ({ isListening, isSupported, onClick, disabled }) => {
  return (
    <button
      data-testid="mic-record-button"
      onClick={onClick}
      disabled={disabled || !isSupported}
      className={`
        mic-button
        ${isListening ? 'recording' : ''}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        ${!isSupported ? 'opacity-30' : ''}
      `}
      aria-label={isListening ? 'Stop recording' : 'Start recording'}
    >
      {isListening ? (
        <MicOff className="w-8 h-8 text-white" />
      ) : (
        <Mic className="w-8 h-8 text-white" />
      )}
    </button>
  );
};

export default MicButton;
