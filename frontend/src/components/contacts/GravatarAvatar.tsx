import React, { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { Avatar } from './Avatar';

interface Props {
  name: string;
  email: string;
  size: number;
}

interface GravatarResult {
  has_avatar: boolean;
  url?: string;
}

const cache = new Map<string, GravatarResult>();

const GravatarAvatar: React.FC<Props> = ({ name, email, size }) => {
  const [imgError, setImgError] = React.useState(false);
  const [result, setResult] = useState<GravatarResult | null>(
    cache.get(email) ?? null
  );

  useEffect(() => {
    if (cache.has(email)) {
      setResult(cache.get(email)!);
      return;
    }

    let cancelled = false;

    api.get<GravatarResult>(`/contacts/gravatar?email=${encodeURIComponent(email)}`)
      .then((data) => {
        cache.set(email, data);
        if (!cancelled) setResult(data);
      })
      .catch(() => {
        const fallback: GravatarResult = { has_avatar: false };
        cache.set(email, fallback);
        if (!cancelled) setResult(fallback);
      });

    return () => { cancelled = true; };
  }, [email]);

  if (result?.has_avatar && result.url && !imgError) {
    return (
      <img
        src={result.url}
        alt={name}
        width={size}
        height={size}
        style={{ borderRadius: '50%', objectFit: 'cover' }}
        onError={() => setImgError(true)}
      />
    );
  }

  return <Avatar name={name} size={size} />;
};

export { GravatarAvatar };
