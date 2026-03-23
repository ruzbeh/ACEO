import { createClientComponentClient } from "@supabase/auth-helpers-nextjs";

const supabase = createClientComponentClient();

/**
 * Upload a file to a Supabase Storage bucket.
 */
export async function uploadFile(
  bucket: string,
  path: string,
  file: File
): Promise<{ path: string; error: Error | null }> {
  const { data, error } = await supabase.storage
    .from(bucket)
    .upload(path, file, {
      contentType: file.type,
      upsert: false,
    });

  if (error) {
    return { path: "", error: new Error(error.message) };
  }

  return { path: data.path, error: null };
}

/**
 * Get the public URL for a file in a Supabase Storage bucket.
 */
export function getPublicUrl(bucket: string, path: string): string {
  const {
    data: { publicUrl },
  } = supabase.storage.from(bucket).getPublicUrl(path);

  return publicUrl;
}

/**
 * Delete a file from a Supabase Storage bucket.
 */
export async function deleteFile(
  bucket: string,
  path: string
): Promise<{ error: Error | null }> {
  const { error } = await supabase.storage.from(bucket).remove([path]);

  if (error) {
    return { error: new Error(error.message) };
  }

  return { error: null };
}
