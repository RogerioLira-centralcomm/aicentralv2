/** Return the signed-in user's profile photo before any generated avatar. */
export function workspaceUserPhoto(user = {}) {
  const value = [user.avatar, user.photoUrl, user.photo_url, user.foto_url, user.picture, user.googlePicture, user.google_picture]
    .find(candidate => typeof candidate === 'string' && candidate.trim());
  if (!value) return '';
  const photo = value.trim();
  if (/^static\//i.test(photo)) return `/${photo}`;
  if (/^(?:https?:|data:|blob:|\/)/i.test(photo)) return photo;
  return `/${photo}`;
}
