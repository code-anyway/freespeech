import { ArrowPathIcon, CloudArrowUpIcon, FingerPrintIcon, LockClosedIcon } from '@heroicons/react/24/outline'

const features = [
  {
    name: 'Transcribe',
    description:
      'submit a video or document link to transcribe, select source language, receive your newly transcribed document!',
    icon: CloudArrowUpIcon,
  },
  {
    name: 'Translate',
    description:
      'submit a video or document link to translate, select source language, select output language, receive your newly translated document!',
    icon: LockClosedIcon,
  },
  {
    name: 'Dub/Voiceover',
    description:
      'submit a video link to dub (translate voice), select source language, select output language, receive your newly dubbed video',
    icon: ArrowPathIcon,
  },
  {
    name: 'Book transcriptions',
    description:
      "Everything you want to know about what you're reading and more.",
    icon: FingerPrintIcon,
  },
]

export default function Features() {
  return (
    <div className="bg-white py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl lg:text-center">
          <h2 className="text-base font-semibold leading-7 text-indigo-600">Learn quicker and more efficiently</h2>
          <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
            Everything Freespeech can help you with
          </p>
          <p className="mt-6 text-lg leading-8 text-gray-600">
            removing language barriers across borders
through video translation
lets get started!
          </p>
        </div>
        <div className="mx-auto mt-16 max-w-2xl sm:mt-20 lg:mt-24 lg:max-w-4xl">
          <dl className="grid max-w-xl grid-cols-1 gap-x-8 gap-y-10 lg:max-w-none lg:grid-cols-2 lg:gap-y-16">
            {features.map((feature) => (
              <div key={feature.name} className="relative pl-16">
                <dt className="text-base font-semibold leading-7 text-gray-900">
                  <div className="absolute left-0 top-0 flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-600">
                    <feature.icon className="h-6 w-6 text-white" aria-hidden="true" />
                  </div>
                  {feature.name}
                </dt>
                <dd className="mt-2 text-base leading-7 text-gray-600">{feature.description}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  )
}
