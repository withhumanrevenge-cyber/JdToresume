import { Suspense } from "react"

import { HomeRedirect } from "./home-redirect"

/** "/" has nothing of its own: signed-in users go to their applications, everyone else to sign-in. */
export default function Home() {
  return (
    <Suspense>
      <HomeRedirect />
    </Suspense>
  )
}
