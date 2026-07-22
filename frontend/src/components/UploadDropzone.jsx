import { useState, useRef, useCallback } from 'react';
import './UploadDropzone.css';

const MAX_MB = 25;
const ACCEPTED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
];

export default function UploadDropzone({ onFileSelected, disabled }) {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const validateAndEmit = useCallback((file) => {
    setError(null);
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError('Only PDF and DOCX files are supported.');
      return;
    }
    if (file.size === 0) {
      setError('This file is empty.');
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File exceeds the ${MAX_MB}MB limit.`);
      return;
    }
    onFileSelected(file);
  }, [onFileSelected]);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    validateAndEmit(file);
  };

  return (
    <div
      className={`dropzone glass ${isDragging ? 'dropzone--active' : ''} ${disabled ? 'dropzone--disabled' : ''}`}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true); }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
      role="button"
      tabIndex={disabled ? -1 : 0}
      aria-disabled={disabled}
      onKeyDown={(e) => {
        if (!disabled && (e.key === 'Enter' || e.key === ' ')) inputRef.current?.click();
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        onChange={(e) => validateAndEmit(e.target.files?.[0])}
        className="visually-hidden"
        disabled={disabled}
      />
      <div className="dropzone__icon" aria-hidden="true">§</div>
      <p className="dropzone__title">
        {disabled ? "You've used all your analyses" : 'Drop a contract here, or click to browse'}
      </p>
      <p className="dropzone__hint">PDF or DOCX, up to {MAX_MB}MB</p>
      {error && <p className="dropzone__error" role="alert">{error}</p>}
    </div>
  );
}
