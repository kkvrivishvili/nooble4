import imageCompression from 'browser-image-compression'

export const compressImage = async (file: Blob): Promise<Blob> => {
  const options = {
    maxSizeMB: 1,
    maxWidthOrHeight: 1024,
    useWebWorker: true,
    preserveExif: true,
    // Maintain original format if possible
    fileType: file instanceof File ? file.type : 'image/jpeg'
  }
  
  try {
    // Convert Blob to File if needed
    const fileToCompress = file instanceof File 
      ? file 
      : new File([file], 'image.jpg', { 
          type: file.type || 'image/jpeg'
        })

    return await imageCompression(fileToCompress, options)
  } catch (error) {
    console.error('Compression failed:', error)
    return file
  }
}

export const createImage = (url: string): Promise<HTMLImageElement> =>
  new Promise((resolve, reject) => {
    const image = new Image()
    image.addEventListener('load', () => resolve(image))
    image.addEventListener('error', reject)
    image.src = url
  })

// Add utility for extracting filename from URL
export const getFileNameFromUrl = (url: string): string => {
  try {
    const urlParts = new URL(url)
    return urlParts.pathname.split('/').pop() || ''
  } catch {
    return ''
  }
}
  